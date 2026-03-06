"""Open Terminal REST API client.

A thin async HTTP client wrapping the Open Terminal REST API for
executing commands, managing files, and checking container health.

Reference: https://github.com/open-webui/open-terminal
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from .lifecycle import TerminalContainer

logger = logging.getLogger(__name__)


# ============================================================================
# Exceptions
# ============================================================================

class TerminalClientError(Exception):
    """Base exception for terminal client errors."""
    pass


class TerminalTimeoutError(TerminalClientError):
    """Raised when a command times out."""
    
    def __init__(self, timeout: float, command: str = ""):
        self.timeout = timeout
        self.command = command
        msg = f"Command timed out after {timeout}s"
        if command:
            msg += f": {command[:100]}"
        super().__init__(msg)


class TerminalAPIError(TerminalClientError):
    """Raised when the terminal API returns an error."""
    
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


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class CommandResult:
    """Result of a command execution.
    
    Attributes:
        exit_code: Shell exit code (0 for success)
        stdout: Standard output from command
        stderr: Standard error from command
        duration_ms: Execution time in milliseconds
    """
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    
    @property
    def success(self) -> bool:
        """True if command exited with code 0."""
        return self.exit_code == 0
    
    def format_output(self) -> str:
        """Format the result for display."""
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
    """Entry in a directory listing.
    
    Attributes:
        name: File or directory name
        path: Full path to the entry
        is_dir: True if directory, False if file
        size: File size in bytes (0 for directories)
        modified: Last modification timestamp (ISO 8601 string)
    """
    name: str
    path: str
    is_dir: bool
    size: int
    modified: str
    
    @classmethod
    def from_dict(cls, data: dict) -> "FileEntry":
        """Create FileEntry from API response dict."""
        return cls(
            name=data.get("name", ""),
            path=data.get("path", ""),
            is_dir=data.get("is_dir", False),
            size=data.get("size", 0),
            modified=data.get("modified", ""),
        )


# ============================================================================
# Terminal Client
# ============================================================================

class TerminalClient:
    """Async HTTP client for Open Terminal REST API.
    
    This client provides methods to interact with a terminal container
    through its REST API endpoints.
    
    Attributes:
        _base_url: Base URL for the terminal API (e.g., http://container:8000)
        _api_key: Bearer token for authentication
        _http: Shared httpx.AsyncClient instance
    
    Example:
        client = TerminalClient(
            base_url="http://if-terminal-abc123:8000",
            api_key="secret-key",
            http_client=httpx.AsyncClient()
        )
        result = await client.execute_command("ls -la")
        print(result.stdout)
    """
    
    DEFAULT_WORKDIR = "/home/user/workspace"
    DEFAULT_TIMEOUT = 120.0
    
    def __init__(
        self,
        base_url: str,
        api_key: str,
        http_client: httpx.AsyncClient,
    ):
        """Initialize the terminal client.
        
        Args:
            base_url: Base URL for the terminal API
            api_key: Bearer token for authentication
            http_client: Shared HTTP client for connection pooling
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http = http_client
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    # ========================================================================
    # Command Execution
    # ========================================================================
    
    async def execute_command(
        self,
        command: str,
        workdir: str = DEFAULT_WORKDIR,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> CommandResult:
        """Execute a shell command in the terminal container.
        
        Args:
            command: Shell command to execute
            workdir: Working directory for the command
            timeout: Maximum execution time in seconds
            
        Returns:
            CommandResult with exit_code, stdout, stderr, duration_ms
            
        Raises:
            TerminalTimeoutError: If command execution times out
            TerminalAPIError: If the API returns an error
        """
        url = f"{self._base_url}/api/execute"
        
        try:
            resp = await self._http.post(
                url,
                headers=self._headers,
                json={"command": command, "workdir": workdir},
                timeout=timeout + 5,  # Add buffer for network latency
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
    
    # ========================================================================
    # File Operations
    # ========================================================================
    
    async def upload_file(
        self,
        remote_path: str,
        content: bytes,
        timeout: float = 30.0,
    ) -> None:
        """Upload a file to the container filesystem.
        
        Args:
            remote_path: Destination path inside the container
            content: File content as bytes
            timeout: Maximum upload time in seconds
            
        Raises:
            TerminalAPIError: If the upload fails
        """
        url = f"{self._base_url}/api/files/upload"
        
        # Extract directory and filename
        dir_path = os.path.dirname(remote_path)
        filename = os.path.basename(remote_path)
        
        try:
            # Use multipart form data
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
        """Upload a text file to the container filesystem.
        
        Convenience method that encodes string content to bytes.
        
        Args:
            remote_path: Destination path inside the container
            content: File content as string
            timeout: Maximum upload time in seconds
        """
        await self.upload_file(remote_path, content.encode("utf-8"), timeout)
    
    async def download_file(
        self,
        remote_path: str,
        timeout: float = 30.0,
    ) -> bytes:
        """Download a file from the container.
        
        Args:
            remote_path: Path to the file inside the container
            timeout: Maximum download time in seconds
            
        Returns:
            Raw file content as bytes
            
        Raises:
            TerminalAPIError: If the download fails
        """
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
        """Download a text file from the container.
        
        Convenience method that decodes bytes to string.
        
        Args:
            remote_path: Path to the file inside the container
            timeout: Maximum download time in seconds
            
        Returns:
            File content as string
        """
        content = await self.download_file(remote_path, timeout)
        return content.decode("utf-8")
    
    async def list_files(
        self,
        path: str = DEFAULT_WORKDIR,
        timeout: float = 30.0,
    ) -> list[FileEntry]:
        """List files and directories in a path.
        
        Args:
            path: Directory to list
            timeout: Maximum request time in seconds
            
        Returns:
            List of FileEntry objects
            
        Raises:
            TerminalAPIError: If the request fails
        """
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
        """Search for files by name pattern.
        
        Args:
            query: Search pattern (e.g., "*.py", "test*")
            path: Directory to search in
            timeout: Maximum request time in seconds
            
        Returns:
            List of matching FileEntry objects
            
        Raises:
            TerminalAPIError: If the request fails
        """
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
    
    # ========================================================================
    # Health Check
    # ========================================================================
    
    async def health(self, timeout: float = 5.0) -> bool:
        """Check if the terminal API is responding.
        
        Args:
            timeout: Maximum time to wait for response
            
        Returns:
            True if healthy, False otherwise
        """
        url = f"{self._base_url}/api/health"
        
        try:
            resp = await self._http.get(url, timeout=timeout)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False


# ============================================================================
# Factory Function
# ============================================================================

def create_terminal_client(
    container: TerminalContainer,
    http_client: httpx.AsyncClient,
) -> TerminalClient:
    """Create a TerminalClient for a specific container.
    
    This is the recommended way to create a TerminalClient instance.
    
    Args:
        container: TerminalContainer with connection details
        http_client: Shared HTTP client for connection pooling
    
    Returns:
        Configured TerminalClient instance
    
    Example:
        container = await lifecycle_manager.get_or_create(conversation_id)
        client = create_terminal_client(container, http_client)
        result = await client.execute_command("ls -la")
    """
    return TerminalClient(
        base_url=container.internal_url,
        api_key=container.api_key,
        http_client=http_client,
    )
