
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from .lifecycle import TerminalContainer

logger = logging.getLogger(__name__)

class TerminalClientError(Exception):

    pass


class TerminalTimeoutError(TerminalClientError):

    
    def __init__(self, timeout: float, command: str = ""):
        self.timeout = timeout
        self.command = command
        msg = f"Command timed out after {timeout}s"
        if command:
            msg += f": {command[:100]}"
        super().__init__(msg)


class TerminalAPIError(TerminalClientError):

    
    def __init__(self, status_code: int, message: str, endpoint: str = ""):
        self.status_code = status_code
        self.message = message
        self.endpoint = endpoint
        msg = f"Terminal API error {status_code}"
        if endpoint:
            msg += f" ({endpoint})"
        if message:
            msg += f": {message}"
        super().__init__(msg)


@dataclass
class CommandResult:

    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    
    @property
    def success(self) -> bool:

        return self.exit_code == 0
    
    def format_output(self) -> str:

        parts = []
        if self.stdout:
            parts.append(f"STDOUT:\n{self.stdout}")
        if self.stderr:
            parts.append(f"STDERR:\n{self.stderr}")
        parts.append(f"EXIT CODE: {self.exit_code}")
        parts.append(f"DURATION: {self.duration_ms}ms")
        return "\n\n".join(parts)


@dataclass
class FileEntry:

    name: str
    path: str
    is_dir: bool
    size: int
    modified: str
    
    @classmethod
    def from_dict(cls, data: dict) -> "FileEntry":

        return cls(
            name=data.get("name", ""),
            path=data.get("path", ""),
            is_dir=data.get("is_dir", False),
            size=data.get("size", 0),
            modified=data.get("modified", ""),
        )


class TerminalClient:

    
    DEFAULT_WORKDIR = "/home/user/workspace"
    DEFAULT_TIMEOUT = 120.0
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        http_client: httpx.AsyncClient,
    ):

        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http = http_client
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    
    async def execute_command(
        self,
        command: str,
        workdir: str = DEFAULT_WORKDIR,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> CommandResult:

        url = f"{self._base_url}/execute"

        try:
            # Start the process (async — returns immediately)
            resp = await self._http.post(
                url,
                headers=self._headers,
                json={"command": command, "cwd": workdir},
                timeout=timeout + 5,
            )
            resp.raise_for_status()
        except httpx.TimeoutException:
            raise TerminalTimeoutError(timeout, command)
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/execute"
            )

        data = resp.json()
        process_id = data.get("id")

        if data.get("status") == "done":
            # Synchronous completion (rare for fast commands)
            return self._parse_execute_result(data)

        # Poll for completion
        status_url = f"{self._base_url}/execute/{process_id}/status"
        poll_interval = 0.5
        elapsed = 0.0

        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            try:
                status_resp = await self._http.get(
                    status_url,
                    headers=self._headers,
                    timeout=timeout + 5,
                )
                status_resp.raise_for_status()
                status_data = status_resp.json()
            except httpx.TimeoutException:
                raise TerminalTimeoutError(timeout, command)
            except httpx.HTTPStatusError as e:
                raise TerminalAPIError(
                    e.response.status_code,
                    e.response.text,
                    endpoint=f"/execute/{process_id}/status",
                )

            if status_data.get("status") == "done":
                return self._parse_execute_result(status_data)

        raise TerminalTimeoutError(timeout, command)

    @staticmethod
    def _parse_execute_result(data: dict) -> CommandResult:
        """Parse an OpenTerminal execute result into a CommandResult.

        The API returns output as [{"type": "output", "data": "..."}] or
        [{"type": "error", "data": "..."}] arrays.
        """
        stdout_parts = []
        stderr_parts = []
        for chunk in data.get("output", []):
            chunk_type = chunk.get("type", "")
            chunk_data = chunk.get("data", "")
            if chunk_type == "error":
                stderr_parts.append(chunk_data)
            else:
                stdout_parts.append(chunk_data)

        return CommandResult(
            exit_code=data.get("exit_code", -1),
            stdout="".join(stdout_parts),
            stderr="".join(stderr_parts),
            duration_ms=0,
        )
    
    
    async def upload_file(
        self,
        remote_path: str,
        content: bytes,
        timeout: float = 30.0,
    ) -> None:

        url = f"{self._base_url}/files/write"

        try:
            resp = await self._http.post(
                url,
                headers=self._headers,
                json={"path": remote_path, "content": content.decode("utf-8", errors="replace")},
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/files/write"
            )

    async def upload_text_file(
        self,
        remote_path: str,
        content: str,
        timeout: float = 30.0,
    ) -> None:

        await self.upload_file(remote_path, content.encode("utf-8"), timeout)
    
    async def download_file(
        self,
        remote_path: str,
        timeout: float = 30.0,
    ) -> bytes:

        url = f"{self._base_url}/files/read"

        try:
            resp = await self._http.get(
                url,
                headers=self._headers,
                params={"path": remote_path},
                timeout=timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("content", "")
            return content.encode("utf-8")
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/files/read"
            )
    
    async def download_text_file(
        self,
        remote_path: str,
        timeout: float = 30.0,
    ) -> str:

        content = await self.download_file(remote_path, timeout)
        return content.decode("utf-8")
    
    async def list_files(
        self,
        path: str = DEFAULT_WORKDIR,
        timeout: float = 30.0,
    ) -> list[FileEntry]:

        url = f"{self._base_url}/files/list"
        
        try:
            resp = await self._http.get(
                url,
                headers=self._headers,
                params={"directory": path},
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/files/list"
            )
        
        data = resp.json()
        entries = data.get("entries", [])
        return [FileEntry.from_dict(entry) for entry in entries]
    
    async def search_files(
        self,
        query: str,
        path: str = DEFAULT_WORKDIR,
        timeout: float = 30.0,
    ) -> list[FileEntry]:

        url = f"{self._base_url}/files/glob"
        
        try:
            resp = await self._http.get(
                url,
                headers=self._headers,
                params={"pattern": query, "path": path},
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/files/glob"
            )
        
        data = resp.json()
        entries = data.get("entries", [])
        return [FileEntry.from_dict(entry) for entry in entries]
    
    
    async def health(self, timeout: float = 5.0) -> bool:

        url = f"{self._base_url}/health"

        try:
            resp = await self._http.get(url, timeout=timeout)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def read_file(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
        timeout: float = 30.0,
    ) -> dict:
        """Read a file with optional line range via the /files/read endpoint.

        Args:
            path: Absolute path to the file
            start_line: 1-indexed start line (inclusive). None for beginning.
            end_line: 1-indexed end line (inclusive). None for end.
            timeout: Request timeout in seconds

        Returns:
            Dict with 'content' key containing file text
        """
        url = f"{self._base_url}/files/read"
        params: dict = {"path": path}
        if start_line is not None:
            params["start_line"] = start_line
        if end_line is not None:
            params["end_line"] = end_line

        try:
            resp = await self._http.get(
                url,
                headers=self._headers,
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/files/read"
            )

    async def write_file(
        self,
        path: str,
        content: str,
        timeout: float = 30.0,
    ) -> None:
        """Write content to a file via the /files/write endpoint.

        Args:
            path: Absolute path to the file
            content: File content as string
            timeout: Request timeout in seconds
        """
        url = f"{self._base_url}/files/write"

        try:
            resp = await self._http.post(
                url,
                headers=self._headers,
                json={"path": path, "content": content},
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/files/write"
            )

    async def grep_files(
        self,
        query: str,
        path: str = ".",
        include: list[str] | None = None,
        case_insensitive: bool = False,
        regex: bool = False,
        match_per_line: bool = True,
        max_results: int = 50,
        timeout: float = 30.0,
    ) -> dict:
        """Search file contents via the /files/grep endpoint.

        Args:
            query: Text or regex pattern to search for
            path: Directory or file to search in
            include: Glob patterns to filter files
            case_insensitive: Case-insensitive matching
            regex: Treat query as regex
            match_per_line: Return matching lines with line numbers
            max_results: Maximum matches to return
            timeout: Request timeout in seconds

        Returns:
            Dict with 'results' key containing match list
        """
        url = f"{self._base_url}/files/grep"
        params: dict = {
            "query": query,
            "path": path,
            "regex": regex,
            "case_insensitive": case_insensitive,
            "match_per_line": match_per_line,
            "max_results": max_results,
        }
        if include:
            params["include"] = include

        try:
            resp = await self._http.get(
                url,
                headers=self._headers,
                params=params,
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/files/grep"
            )



def create_terminal_client(
    container: TerminalContainer,
    http_client: httpx.AsyncClient,
) -> TerminalClient:

    return TerminalClient(
        base_url=container.internal_url,
        api_key=container.api_key,
        http_client=http_client,
    )
