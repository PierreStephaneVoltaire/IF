"""DynamoDB-backed store for training templates.

Templates are date-free reusable programs.
Schema:
    - Template item: pk="operator", sk="template#v{version:03d}"
    - Index item: pk="operator", sk="template#current_list" -> list of template summaries
"""
from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

class TemplateNotFoundError(Exception):
    """Raised when a template is not found."""
    pass

class TemplateStore:
    """DynamoDB-backed store for training templates."""

    INDEX_SK = "template#current_list"
    TEMPLATE_SK_PREFIX = "template#v"

    def __init__(self, table_name: str, pk: str = "operator", region: str = "ca-central-1"):
        self._table_name = table_name
        self._pk = pk
        self._region = region
        self._table = None

    @property
    def table(self):
        if self._table is None:
            self._table = boto3.resource(
                "dynamodb", region_name=self._region
            ).Table(self._table_name)
        return self._table

    def _floats_to_decimals(self, obj: Any) -> Any:
        if isinstance(obj, float):
            return Decimal(str(obj))
        if isinstance(obj, dict):
            return {k: self._floats_to_decimals(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [self._floats_to_decimals(v) for v in obj]
        return obj

    def get_template_sync(self, sk: str) -> dict | None:
        resp = self.table.get_item(Key={"pk": self._pk, "sk": sk})
        if "Item" not in resp:
            return None
        item = dict(resp["Item"])
        item["pk"] = item.get("pk", self._pk)
        item["sk"] = item.get("sk", sk)
        return item

    async def get_template(self, sk: str) -> dict | None:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.get_template_sync(sk)
        )

    def list_templates_sync(self, include_archived: bool = False) -> list[dict]:
        resp = self.table.get_item(Key={"pk": self._pk, "sk": self.INDEX_SK})
        if "Item" not in resp:
            return []
        
        templates = resp["Item"].get("templates", [])
        if not include_archived:
            templates = [t for t in templates if not t.get("archived", False)]
        
        return templates

    async def list_templates(self, include_archived: bool = False) -> list[dict]:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.list_templates_sync(include_archived)
        )

    def put_template_sync(self, template: dict) -> str:
        now = datetime.now(timezone.utc).isoformat()
        
        # Determine next version
        templates = self.list_templates_sync(include_archived=True)
        max_v = 0
        for t in templates:
            sk = t.get("sk", "")
            if sk.startswith(self.TEMPLATE_SK_PREFIX):
                try:
                    v = int(sk[len(self.TEMPLATE_SK_PREFIX):])
                    if v > max_v:
                        max_v = v
                except ValueError:
                    continue
        
        new_v = max_v + 1
        new_sk = f"{self.TEMPLATE_SK_PREFIX}{new_v:03d}"
        
        # Prepare template item
        template_item = copy.deepcopy(template)
        if "meta" not in template_item:
            template_item["meta"] = {}
        
        template_item["meta"]["updated_at"] = now
        if "created_at" not in template_item["meta"]:
            template_item["meta"]["created_at"] = now
            
        template_item["pk"] = self._pk
        template_item["sk"] = new_sk
        
        # Write template
        self.table.put_item(Item=self._floats_to_decimals(template_item))
        
        # Update index
        summary = {
            "sk": new_sk,
            "name": template_item["meta"].get("name"),
            "source_filename": template_item["meta"].get("source_filename"),
            "source_file_hash": template_item["meta"].get("source_file_hash"),
            "estimated_weeks": template_item["meta"].get("estimated_weeks"),
            "days_per_week": template_item["meta"].get("days_per_week"),
            "archived": template_item["meta"].get("archived", False),
            "created_at": template_item["meta"]["created_at"],
            "updated_at": now
        }
        
        # Filter out the old entry if this was somehow an update (though we auto-increment)
        # Actually, templates don't seem to have "minor versions" in the plan, just new versions or new templates.
        # But if we wanted to update a template, we might need a different method.
        # Plan says "put_template(template: dict) -> str # auto-increments vNNN, updates current_list"
        
        templates.append(summary)
        
        index_item = {
            "pk": self._pk,
            "sk": self.INDEX_SK,
            "templates": templates,
            "updated_at": now
        }
        self.table.put_item(Item=self._floats_to_decimals(index_item))
        
        return new_sk

    async def put_template(self, template: dict) -> str:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.put_template_sync(template)
        )

    def archive_template_sync(self, sk: str) -> None:
        template = self.get_template_sync(sk)
        if not template:
            raise TemplateNotFoundError(f"Template not found: {sk}")
        
        template["meta"]["archived"] = True
        template["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        template_item = {**template, "pk": self._pk, "sk": sk}
        self.table.put_item(Item=self._floats_to_decimals(template_item))
        
        # Update index
        templates = self.list_templates_sync(include_archived=True)
        for t in templates:
            if t["sk"] == sk:
                t["archived"] = True
                t["updated_at"] = template["meta"]["updated_at"]
                break
        
        index_item = {
            "pk": self._pk,
            "sk": self.INDEX_SK,
            "templates": templates,
            "updated_at": template["meta"]["updated_at"]
        }
        self.table.put_item(Item=self._floats_to_decimals(index_item))

    async def archive_template(self, sk: str) -> None:
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.archive_template_sync(sk)
        )

    def unarchive_template_sync(self, sk: str) -> None:
        template = self.get_template_sync(sk)
        if not template:
            raise TemplateNotFoundError(f"Template not found: {sk}")
        
        template["meta"]["archived"] = False
        template["meta"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        template_item = {**template, "pk": self._pk, "sk": sk}
        self.table.put_item(Item=self._floats_to_decimals(template_item))
        
        # Update index
        templates = self.list_templates_sync(include_archived=True)
        for t in templates:
            if t["sk"] == sk:
                t["archived"] = False
                t["updated_at"] = template["meta"]["updated_at"]
                break
        
        index_item = {
            "pk": self._pk,
            "sk": self.INDEX_SK,
            "templates": templates,
            "updated_at": template["meta"]["updated_at"]
        }
        self.table.put_item(Item=self._floats_to_decimals(index_item))

    async def unarchive_template(self, sk: str) -> None:
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.unarchive_template_sync(sk)
        )

    def copy_template_sync(self, sk: str, new_name: str) -> str:
        template = self.get_template_sync(sk)
        if not template:
            raise TemplateNotFoundError(f"Template not found: {sk}")
        
        new_template = copy.deepcopy(template)
        new_template["meta"]["name"] = new_name
        new_template["meta"].pop("created_at", None)
        new_template["meta"]["derived_from_template_sk"] = sk
        new_template["meta"]["archived"] = False
        
        return self.put_template_sync(new_template)

    async def copy_template(self, sk: str, new_name: str) -> str:
        return await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.copy_template_sync(sk, new_name)
        )

    def update_template_sync(self, sk: str, template: dict) -> None:
        existing = self.get_template_sync(sk)
        if not existing:
            raise TemplateNotFoundError(f"Template not found: {sk}")

        now = datetime.now(timezone.utc).isoformat()
        template_item = copy.deepcopy(template)
        if "meta" not in template_item:
            template_item["meta"] = {}

        template_item["meta"]["updated_at"] = now
        template_item["meta"]["created_at"] = existing["meta"].get("created_at", now)

        template_item["pk"] = self._pk
        template_item["sk"] = sk
        self.table.put_item(Item=self._floats_to_decimals(template_item))

        # Update index
        templates = self.list_templates_sync(include_archived=True)
        for t in templates:
            if t["sk"] == sk:
                t["name"] = template_item["meta"].get("name", t.get("name"))
                t["estimated_weeks"] = template_item["meta"].get("estimated_weeks", t.get("estimated_weeks"))
                t["days_per_week"] = template_item["meta"].get("days_per_week", t.get("days_per_week"))
                t["archived"] = template_item["meta"].get("archived", t.get("archived", False))
                t["updated_at"] = now
                break

        index_item = {
            "pk": self._pk,
            "sk": self.INDEX_SK,
            "templates": templates,
            "updated_at": now,
        }
        self.table.put_item(Item=self._floats_to_decimals(index_item))

    async def update_template(self, sk: str, template: dict) -> None:
        await asyncio.get_running_loop().run_in_executor(
            None, lambda: self.update_template_sync(sk, template)
        )
