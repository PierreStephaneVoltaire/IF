from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from channels.execution_models import DiscordOutboundMessage, floats_to_decimals
from config import IF_EXECUTION_REGISTRY_TABLE_NAME, AWS_REGION, EXECUTION_REGISTRY_TTL_OUTBOX_SECONDS

logger = logging.getLogger(__name__)
_store: Optional[ExecutionStore] = None


def _ttl_epoch(seconds: int) -> int:
    return int(datetime.now(timezone.utc).timestamp()) + seconds


def get_execution_store() -> ExecutionStore:
    global _store
    if _store is None:
        _store = ExecutionStore()
    return _store


class ExecutionStore:
    def __init__(
        self,
        table_name: str = IF_EXECUTION_REGISTRY_TABLE_NAME,
        region: str = AWS_REGION,
    ):
        self.table_name = table_name
        self._region = region
        self._table = None

    @property
    def table(self):
        if self._table is None:
            self._table = boto3.resource(
                "dynamodb", region_name=self._region
            ).Table(self.table_name)
        return self._table

    async def put_outbound_message(self, msg: DiscordOutboundMessage) -> bool:
        return await asyncio.to_thread(self._put_outbound_message_sync, msg)

    def _put_outbound_message_sync(self, msg: DiscordOutboundMessage) -> bool:
        pk = f"CHANNEL#{msg.channel_id}"
        priority_padded = f"{msg.priority:02d}"
        send_after = msg.send_after or msg.created_at or datetime.now(timezone.utc).isoformat()
        sk = f"OUTBOX#{priority_padded}#{send_after}#{msg.outbound_id}"
        idem_sk = f"OUTBOX_IDEMPOTENCY#{msg.idempotency_key}"
        item: Dict[str, Any] = {
            "pk": pk,
            "sk": sk,
            "outbound_id": msg.outbound_id,
            "channel_id": msg.channel_id,
            "conversation_id": msg.conversation_id,
            "task_id": msg.task_id or "",
            "intent_id": msg.intent_id or "",
            "batch_id": msg.batch_id or "",
            "type": msg.type,
            "priority": msg.priority,
            "content": msg.content,
            "attachments": msg.attachments,
            "reply_to_message_id": msg.reply_to_message_id or "",
            "status": msg.status,
            "send_after": msg.send_after or "",
            "created_at": msg.created_at,
            "updated_at": msg.updated_at,
            "discord_message_id": msg.discord_message_id or "",
            "idempotency_key": msg.idempotency_key,
        }
        if msg.allowed_mentions is not None:
            item["allowed_mentions"] = msg.allowed_mentions
        outbox_ttl = msg.ttl if msg.ttl is not None else _ttl_epoch(EXECUTION_REGISTRY_TTL_OUTBOX_SECONDS)
        item["ttl"] = outbox_ttl
        try:
            idem_item: Dict[str, Any] = {
                "pk": pk,
                "sk": idem_sk,
                "idempotency_key": msg.idempotency_key,
                "outbound_id": msg.outbound_id,
                "created_at": msg.created_at,
                "updated_at": msg.updated_at,
                "ttl": outbox_ttl,
            }
            self._transact_put_items(
                [
                    (idem_item, "attribute_not_exists(pk)"),
                    (item, "attribute_not_exists(pk)"),
                ]
            )
            return True
        except ClientError as e:
            reasons = {reason.get("Code") for reason in e.response.get("CancellationReasons", [])} - {"None", None}
            duplicate = e.response["Error"]["Code"] == "ConditionalCheckFailedException" or (e.response["Error"]["Code"] == "TransactionCanceledException" and reasons == {"ConditionalCheckFailed"})
            if duplicate:
                logger.warning(
                    "Outbound enqueue blocked: outbound_id=%s idempotency_key=%s msg_type=%s",
                    msg.outbound_id,
                    msg.idempotency_key,
                    msg.type,
                )
                return False
            logger.error(
                "Outbound transaction error (non-idempotency): %s %s outbound_id=%s key=%s",
                e.response.get("Error", {}).get("Code", "?"),
                e.response.get("Error", {}).get("Message", "")[:200],
                msg.outbound_id,
                msg.idempotency_key,
            )
            raise

    def _transact_put_items(
        self, items: List[tuple[Dict[str, Any], str]]
    ) -> None:
        transact_items = []
        for item, condition in items:
            transact_items.append(
                {
                    "Put": {
                        "TableName": self.table_name,
                        "Item": floats_to_decimals(item),
                        "ConditionExpression": condition,
                    }
                }
            )
        dynamodb = boto3.resource("dynamodb", region_name=self._region)
        dynamodb.meta.client.transact_write_items(TransactItems=transact_items)

    @staticmethod
    def _item_to_outbound_message(item: Dict[str, Any]) -> DiscordOutboundMessage:
        return DiscordOutboundMessage(
            outbound_id=item.get("outbound_id", ""),
            channel_id=item.get("channel_id", ""),
            conversation_id=item.get("conversation_id", ""),
            task_id=item.get("task_id") or None,
            intent_id=item.get("intent_id") or None,
            batch_id=item.get("batch_id") or None,
            type=item.get("type", "social_response"),
            priority=int(item.get("priority", 5)),
            content=item.get("content", ""),
            attachments=item.get("attachments", []),
            reply_to_message_id=item.get("reply_to_message_id") or None,
            allowed_mentions=item.get("allowed_mentions"),
            status=item.get("status", "queued"),
            send_after=item.get("send_after") or None,
            created_at=item.get("created_at", ""),
            updated_at=item.get("updated_at", ""),
            discord_message_id=item.get("discord_message_id") or None,
            idempotency_key=item.get("idempotency_key", ""),
            ttl=item.get("ttl"),
            registry_sk=item.get("sk"),
        )

    async def acquire_outbound_lock(
        self, channel_id: str, owner: str, expires_at: str
    ) -> bool:
        return await asyncio.to_thread(
            self._acquire_outbound_lock_sync, channel_id, owner, expires_at
        )

    def _acquire_outbound_lock_sync(
        self, channel_id: str, owner: str, expires_at: str
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        pk = f"CHANNEL#{channel_id}"
        sk = "STATE#outbound"
        try:
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression=(
                    "SET outbound_lock_owner = :owner,"
                    " outbound_lock_expires_at = :expires,"
                    " updated_at = :now"
                ),
                ConditionExpression=(
                    "attribute_not_exists(outbound_lock_owner)"
                    " OR outbound_lock_expires_at < :now_str"
                ),
                ExpressionAttributeValues={
                    ":owner": owner,
                    ":expires": expires_at,
                    ":now": now,
                    ":now_str": now,
                },
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info("Outbound lock acquisition failed for channel %s", channel_id)
                return False
            raise

    async def release_outbound_lock(
        self, channel_id: str, owner: str
    ) -> bool:
        return await asyncio.to_thread(
            self._release_outbound_lock_sync, channel_id, owner
        )

    def _release_outbound_lock_sync(
        self, channel_id: str, owner: str
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        pk = f"CHANNEL#{channel_id}"
        sk = "STATE#outbound"
        try:
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression="REMOVE outbound_lock_owner, outbound_lock_expires_at SET updated_at = :now",
                ConditionExpression="outbound_lock_owner = :owner",
                ExpressionAttributeValues={":owner": owner, ":now": now},
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info(
                    "Outbound lock release failed for channel %s (owner mismatch)",
                    channel_id,
                )
                return False
            raise

    async def get_outbound_state(
        self, channel_id: str
    ) -> Optional[Dict[str, Any]]:
        return await asyncio.to_thread(self._get_outbound_state_sync, channel_id)

    def _get_outbound_state_sync(
        self, channel_id: str
    ) -> Optional[Dict[str, Any]]:
        resp = self.table.get_item(
            Key={"pk": f"CHANNEL#{channel_id}", "sk": "STATE#outbound"}
        )
        return resp.get("Item")

    async def query_outbox(
        self, channel_id: str, limit: int = 10
    ) -> List[DiscordOutboundMessage]:
        return await asyncio.to_thread(self._query_outbox_sync, channel_id, limit)

    def _query_outbox_sync(
        self, channel_id: str, limit: int
    ) -> List[DiscordOutboundMessage]:
        pk = f"CHANNEL#{channel_id}"
        messages: List[DiscordOutboundMessage] = []
        last_key = None
        pages = 0
        now = datetime.now(timezone.utc)
        try:
            while len(messages) < limit and pages < 100:
                pages += 1
                kwargs: Dict[str, Any] = {
                    "KeyConditionExpression": "pk = :pk AND begins_with(sk, :prefix)",
                    "ExpressionAttributeValues": {
                        ":pk": pk,
                        ":prefix": "OUTBOX#",
                    },
                    "Limit": max(limit * 4, 25),
                    "ScanIndexForward": True,
                }
                if last_key:
                    kwargs["ExclusiveStartKey"] = last_key
                resp = self.table.query(**kwargs)
                for item in resp.get("Items", []):
                    if item.get("status") != "queued":
                        continue
                    send_after = item.get("send_after") or ""
                    if send_after:
                        try:
                            send_after_dt = datetime.fromisoformat(send_after)
                            if send_after_dt > now:
                                continue
                        except (ValueError, TypeError):
                            pass
                    messages.append(self._item_to_outbound_message(item))
                    if len(messages) >= limit:
                        break
                last_key = resp.get("LastEvaluatedKey")
                if not last_key:
                    break
            return messages
        except ClientError:
            logger.exception("Failed to query outbox for channel %s", channel_id)
            return []

    async def update_outbound_message_status(
        self,
        channel_id: str,
        outbound_id: str,
        from_status: str,
        to_status: str,
        registry_sk: str | None = None,
        **extra_updates: Any,
    ) -> bool:
        return await asyncio.to_thread(
            self._update_outbound_status_sync,
            channel_id,
            outbound_id,
            from_status,
            to_status,
            registry_sk,
            **extra_updates,
        )

    def _update_outbound_status_sync(
        self,
        channel_id: str,
        outbound_id: str,
        from_status: str,
        to_status: str,
        registry_sk: str | None = None,
        **extra_updates: Any,
    ) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        pk = f"CHANNEL#{channel_id}"
        update_parts = ["#st = :to_status", "updated_at = :now"]
        attr_names = {"#st": "status"}
        attr_values: Dict[str, Any] = {
            ":to_status": to_status,
            ":from_status": from_status,
            ":now": now,
        }
        for k, v in extra_updates.items():
            update_parts.append(f"{k} = :eu_{k}")
            attr_values[f":eu_{k}"] = floats_to_decimals(v)
        try:
            sk = registry_sk or self._find_outbound_sk(pk, outbound_id)
            if not sk:
                logger.warning(
                    "Outbound message %s not found for status update", outbound_id
                )
                return False
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression="SET " + ", ".join(update_parts),
                ConditionExpression="#st = :from_status",
                ExpressionAttributeNames=attr_names,
                ExpressionAttributeValues=attr_values,
            )
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.info(
                    "Outbound status %s->%s failed for %s (condition)",
                    from_status,
                    to_status,
                    outbound_id,
                )
                return False
            raise

    def _find_outbound_sk(self, pk: str, outbound_id: str) -> Optional[str]:
        last_key = None
        pages = 0
        while pages < 100:
            pages += 1
            kwargs: Dict[str, Any] = {
                "KeyConditionExpression": "pk = :pk AND begins_with(sk, :prefix)",
                "ExpressionAttributeValues": {
                    ":pk": pk,
                    ":prefix": "OUTBOX#",
                },
                "ProjectionExpression": "sk, outbound_id",
                "Limit": 100,
                "ScanIndexForward": True,
            }
            if last_key:
                kwargs["ExclusiveStartKey"] = last_key
            resp = self.table.query(**kwargs)
            for item in resp.get("Items", []):
                if item.get("outbound_id") == outbound_id:
                    return item.get("sk")
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                return None
        return None
