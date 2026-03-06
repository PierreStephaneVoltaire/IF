
from __future__ import annotations

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

        url = f"{self._base_url}/api/execute"
        
        try:
            resp = await self._http.post(
                url,
                headers=self._headers,
                json={"command": command, "workdir": workdir},
                timeout=timeout + 5,
            )
            resp.raise_for_status()
        except httpx.TimeoutException:
            raise TerminalTimeoutError(timeout, command)
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/api/execute"
            )
        
        data = resp.json()
        return CommandResult(
            exit_code=data.get("exit_code", -1),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            duration_ms=data.get("duration_ms", 0),
        )
    
    
    async def upload_file(
        self,
        remote_path: str,
        content: bytes,
        timeout: float = 30.0,
    ) -> None:

        url = f"{self._base_url}/api/files/upload"
        
        dir_path = os.path.dirname(remote_path)
        filename = os.path.basename(remote_path)
        
        try:
            files = {"file": (filename, content)}
            data = {"path": dir_path}
            
            resp = await self._http.post(
                url,
                headers={"Authorization": f"Bearer {self._api_key}"},
                files=files,
                data=data,
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/api/files/upload"
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

        url = f"{self._base_url}/api/files/download"
        
        try:
            resp = await self._http.get(
                url,
                headers=self._headers,
                params={"path": remote_path},
                timeout=timeout,
            )
            resp.raise_for_status()
            return resp.content
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/api/files/download"
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

        url = f"{self._base_url}/api/files/list"
        
        try:
            resp = await self._http.get(
                url,
                headers=self._headers,
                params={"path": path},
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/api/files/list"
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

        url = f"{self._base_url}/api/files/search"
        
        try:
            resp = await self._http.get(
                url,
                headers=self._headers,
                params={"query": query, "path": path},
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise TerminalAPIError(
                e.response.status_code,
                e.response.text,
                endpoint="/api/files/search"
            )
        
        data = resp.json()
        entries = data.get("entries", [])
        return [FileEntry.from_dict(entry) for entry in entries]
    
    
    async def health(self, timeout: float = 5.0) -> bool:

        url = f"{self._base_url}/api/health"
        
        try:
            resp = await self._http.get(url, timeout=timeout)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False



def create_terminal_client(
    container: TerminalContainer,
    http_client: httpx.AsyncClient,
) -> TerminalClient:

    return TerminalClient(
        base_url=container.internal_url,
        api_key=container.api_key,
        http_client=http_client,
    )
