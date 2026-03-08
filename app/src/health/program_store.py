"""DynamoDB-backed store for training programs.

Uses a pointer-based schema to track the current program version.
Pointer item: pk=HEALTH_PROGRAM_PK, sk="program#current" -> {version, ref_sk, updated_at}
Program item: pk=HEALTH_PROGRAM_PK, sk="program#v{version:03d}" -> full program JSON
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger(__name__)


class ProgramNotFoundError(Exception):
    """Raised when pointer item does not exist in DynamoDB."""
    pass


class ProgramStore:
    """DynamoDB-backed store for training programs with versioning support.
    
    Schema:
        - Pointer item: pk=HEALTH_PROGRAM_PK, sk="program#current"
          -> {version: int, ref_sk: str, updated_at: ISO8601}
        - Program item: pk=HEALTH_PROGRAM_PK, sk="program#v{version:03d}"
          -> full program JSON as DynamoDB map
    
    All operations are cached in memory for performance.
    """
    
    POINTER_SK = "program#current"
    PROGRAM_SK_PREFIX = "program#v"
    
    def __init__(self, table_name: str, pk: str = "operator"):
        """Initialize the program store.
        
        Args:
            table_name: Name of the DynamoDB table
            pk: Partition key value (default: "operator")
        """
        self._table_name = table_name
        self._pk = pk
        self._table = boto3.resource("dynamodb").Table(table_name)
        self._cache: Optional[dict] = None
        self._cache_version: Optional[int] = None
        
        logger.debug(f"[ProgramStore] Initialized with table={table_name}, pk={pk}")
    
    def invalidate_cache(self) -> None:
        """Clear the in-memory cache."""
        logger.debug("[ProgramStore] Cache invalidated")
        self._cache = None
        self._cache_version = None
    
    async def get_program(self) -> dict:
        """Get the current training program.
        
        Returns cached program if available, otherwise loads from DynamoDB.
        
        Returns:
            Full program dict
            
        Raises:
            ProgramNotFoundError: If pointer item does not exist
            RuntimeError: If DynamoDB operation fails
        """
        if self._cache is not None:
            logger.debug("[ProgramStore] Cache hit, returning cached program")
            return self._cache
        
        logger.debug("[ProgramStore] Cache miss, loading from DynamoDB")
        
        try:
            # Run synchronous DynamoDB operations in executor
            program = await asyncio.get_running_loop().run_in_executor(
                None, self._load_program_sync
            )
            
            self._cache = program
            return program
            
        except ProgramNotFoundError:
            raise
        except Exception as e:
            logger.error(f"[ProgramStore] Failed to load program: {e}")
            raise RuntimeError(f"Failed to load program from DynamoDB: {e}")
    
    def _load_program_sync(self) -> dict:
        """Synchronous program loading logic."""
        # Read pointer item
        logger.debug(f"[ProgramStore] Reading pointer: pk={self._pk}, sk={self.POINTER_SK}")
        pointer_resp = self._table.get_item(
            Key={"pk": self._pk, "sk": self.POINTER_SK}
        )
        
        if "Item" not in pointer_resp:
            logger.warning(f"[ProgramStore] Pointer item not found: pk={self._pk}")
            raise ProgramNotFoundError(
                f"No program pointer found for pk={self._pk}. "
                "Create a program using new_version() first."
            )
        
        pointer = pointer_resp["Item"]
        version = pointer.get("version", 0)
        ref_sk = pointer.get("ref_sk", f"{self.PROGRAM_SK_PREFIX}{version:03d}")
        
        logger.debug(f"[ProgramStore] Pointer points to version={version}, ref_sk={ref_sk}")
        
        # Read program item
        logger.debug(f"[ProgramStore] Reading program: pk={self._pk}, sk={ref_sk}")
        program_resp = self._table.get_item(
            Key={"pk": self._pk, "sk": ref_sk}
        )
        
        if "Item" not in program_resp:
            logger.error(f"[ProgramStore] Program item not found: pk={self._pk}, sk={ref_sk}")
            raise RuntimeError(
                f"Program item not found at {ref_sk}. "
                "Data inconsistency: pointer exists but program item missing."
            )
        
        program = dict(program_resp["Item"])
        # Remove DynamoDB keys from returned program
        program.pop("pk", None)
        program.pop("sk", None)
        
        self._cache_version = version
        logger.debug(f"[ProgramStore] Loaded program version {version}")
        
        return program
    
    async def update_session(self, date: str, patch: dict) -> dict:
        """Update a session by date with the given patch.
        
        Creates a new minor version of the program.
        
        Args:
            date: ISO8601 date string of the session to update
            patch: Dict with session fields to update
            
        Returns:
            Updated program dict
            
        Raises:
            ValueError: If session not found or patch invalid
            RuntimeError: If DynamoDB operation fails
        """
        # Get current program (from cache or DynamoDB)
        program = await self.get_program()
        
        # Deep copy for modification
        new_program = copy.deepcopy(program)
        
        # Find session by date
        sessions = new_program.get("sessions", [])
        session_idx = None
        for i, session in enumerate(sessions):
            if session.get("date") == date:
                session_idx = i
                break
        
        if session_idx is None:
            raise ValueError(f"Session not found with date={date}")
        
        # Apply patch to session fields only
        session = sessions[session_idx]
        for key, value in patch.items():
            session[key] = value
        
        # Write new minor version
        updated_program = await self._write_new_version(new_program, minor=True)
        
        return updated_program
    
    async def new_version(self, patches: list[dict], change_reason: str) -> dict:
        """Create a new major version of the program with patches.
        
        Args:
            patches: List of patches, each with "path" and "value" keys
                    Example: {"path": "sessions[0].exercises[1].kg", "value": 180}
            change_reason: Human-readable reason for the version change
            
        Returns:
            New program dict
            
        Raises:
            ValueError: If patch path is invalid
            RuntimeError: If DynamoDB operation fails
        """
        # Get current program (from cache or DynamoDB)
        program = await self.get_program()
        
        # Deep copy for modification
        new_program = copy.deepcopy(program)
        
        # Apply each patch
        for patch in patches:
            path = patch.get("path", "")
            value = patch.get("value")
            
            if not path:
                raise ValueError("Patch must have 'path' key")
            
            self._apply_patch(new_program, path, value)
        
        # Add change reason to meta
        if "meta" not in new_program:
            new_program["meta"] = {}
        if "change_log" not in new_program["meta"]:
            new_program["meta"]["change_log"] = []
        new_program["meta"]["change_log"].append({
            "reason": change_reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        
        # Write new major version
        updated_program = await self._write_new_version(new_program, minor=False)
        
        return updated_program
    
    def _apply_patch(self, obj: dict, path: str, value: Any) -> None:
        """Apply a JSON-path-like patch to an object.
        
        Supports paths like:
            - "sessions[0].exercises[1].kg"
            - "meta.comp_date"
            - "phases[2].end_week"
        
        Args:
            obj: Object to patch
            path: Path to the field to update
            value: New value
            
        Raises:
            ValueError: If path is invalid
        """
        import re
        
        # Parse path into segments
        segments = []
        for part in path.split("."):
            # Handle array indices: sessions[0] -> ("sessions", 0)
            match = re.match(r"^(\w+)\[(\d+)\]$", part)
            if match:
                segments.append((match.group(1), int(match.group(2))))
            else:
                segments.append((part, None))
        
        # Navigate to parent and set value
        current = obj
        for i, (key, idx) in enumerate(segments[:-1]):
            if idx is not None:
                # Array access
                if key not in current:
                    raise ValueError(f"Invalid path '{path}': '{key}' not found")
                if not isinstance(current[key], list):
                    raise ValueError(f"Invalid path '{path}': '{key}' is not a list")
                if idx >= len(current[key]):
                    raise ValueError(f"Invalid path '{path}': index {idx} out of range")
                current = current[key][idx]
            else:
                # Dict access
                if not isinstance(current, dict):
                    raise ValueError(f"Invalid path '{path}': expected dict at '{key}'")
                if key not in current:
                    raise ValueError(f"Invalid path '{path}': '{key}' not found")
                current = current[key]
        
        # Set final value
        final_key, final_idx = segments[-1]
        if final_idx is not None:
            if final_key not in current:
                raise ValueError(f"Invalid path '{path}': '{final_key}' not found")
            if not isinstance(current[final_key], list):
                raise ValueError(f"Invalid path '{path}': '{final_key}' is not a list")
            if final_idx >= len(current[final_key]):
                raise ValueError(f"Invalid path '{path}': index {final_idx} out of range")
            current[final_key][final_idx] = value
        else:
            if not isinstance(current, dict):
                raise ValueError(f"Invalid path '{path}': expected dict at '{final_key}'")
            current[final_key] = value
    
    async def _write_new_version(self, program: dict, minor: bool) -> dict:
        """Write a new version of the program to DynamoDB.
        
        Args:
            program: Program dict to write
            minor: If True, increment minor version (1.0 -> 1.1)
                   If False, increment major version (1.0 -> 2.0)
            
        Returns:
            The written program dict
            
        Raises:
            RuntimeError: If DynamoDB operation fails
        """
        try:
            # Run synchronous DynamoDB operations in executor
            result = await asyncio.get_running_loop().run_in_executor(
                None, lambda: self._write_new_version_sync(program, minor)
            )
            return result
        except Exception as e:
            logger.error(f"[ProgramStore] Failed to write new version: {e}")
            raise RuntimeError(f"Failed to write new version to DynamoDB: {e}")
    
    def _write_new_version_sync(self, program: dict, minor: bool) -> dict:
        """Synchronous version writing logic."""
        now = datetime.now(timezone.utc).isoformat()
        
        # Get current version from pointer
        logger.debug(f"[ProgramStore] Reading current pointer for version increment")
        pointer_resp = self._table.get_item(
            Key={"pk": self._pk, "sk": self.POINTER_SK}
        )
        
        if "Item" in pointer_resp:
            current_version = pointer_resp["Item"].get("version", 0)
        else:
            current_version = 0
        
        # Calculate new version
        new_version_int = current_version + 1
        
        # Version label (for display purposes)
        if "meta" not in program:
            program["meta"] = {}
        
        current_label = program["meta"].get("version_label", "0.0")
        try:
            major, minor_num = map(int, current_label.split("."))
            if minor:
                new_label = f"{major}.{minor_num + 1}"
            else:
                new_label = f"{major + 1}.0"
        except (ValueError, AttributeError):
            new_label = "1.0" if current_version == 0 else f"{new_version_int}.0"
        
        program["meta"]["version_label"] = new_label
        program["meta"]["updated_at"] = now
        
        # Create new program item
        new_sk = f"{self.PROGRAM_SK_PREFIX}{new_version_int:03d}"
        
        program_item = {
            "pk": self._pk,
            "sk": new_sk,
            **program
        }
        
        logger.debug(f"[ProgramStore] Writing new program version: sk={new_sk}, label={new_label}")
        self._table.put_item(Item=program_item)
        
        # Update pointer
        pointer_item = {
            "pk": self._pk,
            "sk": self.POINTER_SK,
            "version": new_version_int,
            "ref_sk": new_sk,
            "updated_at": now,
        }
        
        logger.debug(f"[ProgramStore] Updating pointer to version={new_version_int}")
        self._table.put_item(Item=pointer_item)
        
        # Update cache
        self._cache = program
        self._cache_version = new_version_int
        
        logger.info(f"[ProgramStore] Created new {'minor' if minor else 'major'} version: {new_label} (v{new_version_int})")
        
        return program
