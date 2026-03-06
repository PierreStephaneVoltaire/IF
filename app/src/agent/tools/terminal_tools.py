
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

from terminal import (
    CommandResult,
    create_terminal_client,
    get_lifecycle_manager,
    TerminalContainer,
    TerminalLifecycleManager,
)

from functools import partial

if TYPE_CHECKING:
    from openhands.sdk import Tool

logger = logging.getLogger(__name__)



MAX_OUTPUT_LENGTH = 8000

DEFAULT_WORKDIR = "/home/user/workspace"

DEFAULT_TIMEOUT = 120.0



def truncate_output(output: str, max_length: int = MAX_OUTPUT_LENGTH) -> str:

    if len(output) <= max_length:
        return output
    
    half = max_length // 2
    truncated_count = len(output) - max_length
    return (
        output[:half] + 
        f"\n\n... [{truncated_count} chars truncated] ...\n\n" + 
        output[-half:]
    )


def format_command_result(result: CommandResult) -> str:

    output_parts = []
    
    if result.stdout:
        output_parts.append(f"STDOUT:\n{result.stdout}")
    
    if result.stderr:
        output_parts.append(f"STDERR:\n{result.stderr}")
    
    output_parts.append(f"EXIT CODE: {result.exit_code}")
    output_parts.append(f"DURATION: {result.duration_ms}ms")
    
    output = "\n\n".join(output_parts)
    return truncate_output(output)



async def terminal_execute(
    command: str,
    workdir: str = DEFAULT_WORKDIR,
    timeout: float = DEFAULT_TIMEOUT,
    *,
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:

    try:
        lifecycle = get_lifecycle_manager()
        if lifecycle is None:
            return "ERROR: Terminal system not initialized"
        
        container = await lifecycle.get_or_create(chat_id)
        
        should_close = False
        if http_client is None:
            http_client = httpx.AsyncClient()
            should_close = True
        
        try:
            client = create_terminal_client(container, http_client)
            
            result = await client.execute_command(
                command,
                workdir=workdir,
                timeout=timeout,
            )
            
            return format_command_result(result)
            
        finally:
            if should_close:
                await http_client.aclose()
            
    except httpx.TimeoutException:
        return f"ERROR: Command timed out after {timeout}s"
    
    except httpx.HTTPStatusError as e:
        return f"ERROR: Terminal API returned {e.response.status_code}: {e.response.text}"
    
    except Exception as e:
        logger.error(f"[terminal_execute] Error: {e}")
        return f"ERROR: {type(e).__name__}: {e}"


async def terminal_upload(
    path: str,
    content: str,
    *,
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:

    try:
        lifecycle = get_lifecycle_manager()
        if lifecycle is None:
            return "ERROR: Terminal system not initialized"
        
        container = await lifecycle.get_or_create(chat_id)
        
        if not path.startswith("/"):
            path = f"{DEFAULT_WORKDIR}/{path}"
        
        should_close = False
        if http_client is None:
            http_client = httpx.AsyncClient()
            should_close = True
        
        try:
            client = create_terminal_client(container, http_client)
            
            await client.upload_text_file(path, content)
            
            return f"File uploaded successfully: {path}"
            
        finally:
            if should_close:
                await http_client.aclose()
            
    except httpx.HTTPStatusError as e:
        return f"ERROR: Terminal API returned {e.response.status_code}: {e.response.text}"
    
    except Exception as e:
        logger.error(f"[terminal_upload] Error: {e}")
        return f"ERROR: {type(e).__name__}: {e}"


async def terminal_list_files(
    path: str = DEFAULT_WORKDIR,
    *,
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:

    try:
        lifecycle = get_lifecycle_manager()
        if lifecycle is None:
            return "ERROR: Terminal system not initialized"
        
        container = await lifecycle.get_or_create(chat_id)
        
        should_close = False
        if http_client is None:
            http_client = httpx.AsyncClient()
            should_close = True
        
        try:
            client = create_terminal_client(container, http_client)
            
            entries = await client.list_files(path)
            
            if not entries:
                return f"Directory {path} is empty or does not exist."
            
            lines = [
                "NAME".ljust(40) + "TYPE".ljust(8) + "SIZE".ljust(12) + "MODIFIED",
            ]
            
            for entry in sorted(entries, key=lambda e: (not e.is_dir, e.name)):
                entry_type = "DIR" if entry.is_dir else "FILE"
                name = entry.name + "/" if entry.is_dir else entry.name
                size = str(entry.size) if not entry.is_dir else "-"
                modified_str = entry.modified[:19] if entry.modified else ""
                lines.append(
                    name[:40].ljust(40) +
                    entry_type.ljust(8) +
                    size.ljust(12) +
                    modified_str
                )
            
            return "\n".join(lines)
            
        finally:
            if should_close:
                await http_client.aclose()
            
    except httpx.HTTPStatusError as e:
        return f"ERROR: Terminal API returned {e.response.status_code}: {e.response.text}"
    
    except Exception as e:
        logger.error(f"[terminal_list_files] Error: {e}")
        return f"ERROR: {type(e).__name__}: {e}"


async def terminal_download(
    path: str,
    *,
    chat_id: str,
    http_client: Optional[httpx.AsyncClient] = None,
) -> str:

    try:
        lifecycle = get_lifecycle_manager()
        if lifecycle is None:
            return "ERROR: Terminal system not initialized"
        
        container = await lifecycle.get_or_create(chat_id)
        
        if not path.startswith("/"):
            path = f"{DEFAULT_WORKDIR}/{path}"
        
        should_close = False
        if http_client is None:
            http_client = httpx.AsyncClient()
            should_close = True
        
        try:
            client = create_terminal_client(container, http_client)
            
            content = await client.download_text_file(path)
            
            if len(content) > MAX_OUTPUT_LENGTH:
                content = truncate_output(content)
                content = f"[File truncated - {len(content)} chars shown]\n\n{content}"
            
            return content
            
        finally:
            if should_close:
                await http_client.aclose()
            
    except httpx.HTTPStatusError as e:
        return f"ERROR: Terminal API returned {e.response.status_code}: {e.response.text}"
    
    except Exception as e:
        logger.error(f"[terminal_download] Error: {e}")
        return f"ERROR: {type(e).__name__}: {e}"



def get_terminal_tools(chat_id: str) -> List[Tool]:

    from openhands.sdk import Tool
    
    tools = []
    
    tools.append(Tool(
        name="terminal_execute",
        description="""Execute a shell command in the persistent terminal environment.

The terminal preserves state across calls (installed packages, environment variables, running processes). Working directory is /home/user/workspace by default.

Use this for:
- Running code and scripts
- Installing packages (pip, apt-get, npm)
- Git operations
- File manipulation
- Build commands and test suites
- Data processing

After completing work that creates or modifies files, remember to list them with terminal_list_files.""",
        parameters={
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute. Can be a single command or a multi-line script. Supports pipes, redirects, and chaining (&&, ||, ;)."
                },
                "workdir": {
                    "type": "string",
                    "description": "Working directory for the command. Defaults to /home/user/workspace.",
                    "default": "/home/user/workspace"
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximum execution time in seconds. Defaults to 120.",
                    "default": 120
                }
            },
            "required": ["command"]
        },
        function=partial(terminal_execute, chat_id=chat_id),
    ))
    
    tools.append(Tool(
        name="terminal_upload",
        description="""Upload a file to the terminal workspace.

Use this to provide data files, scripts, or configuration that the terminal needs. For text files only.""",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Destination path inside the terminal. Relative paths are resolved from /home/user/workspace."
                },
                "content": {
                    "type": "string",
                    "description": "File content as a string."
                }
            },
            "required": ["path", "content"]
        },
        function=partial(terminal_upload, chat_id=chat_id),
    ))
    
    tools.append(Tool(
        name="terminal_list_files",
        description="""List files and directories in the terminal workspace.

Returns names, sizes, and modification times. Use this to explore the workspace and find files created by commands.""",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory to list. Defaults to /home/user/workspace.",
                    "default": "/home/user/workspace"
                }
            }
        },
        function=partial(terminal_list_files, chat_id=chat_id),
    ))
    
    tools.append(Tool(
        name="terminal_download",
        description="""Download a file from the terminal workspace.

Use this to retrieve file contents. For text files only. For large files, consider using terminal_execute with head/tail.""",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file inside the terminal. Relative paths are resolved from /home/user/workspace."
                }
            },
            "required": ["path"]
        },
        function=partial(terminal_download, chat_id=chat_id),
    ))
    
    return tools



TERMINAL_SYSTEM_PROMPT = """

You have a persistent Linux terminal accessible via the `terminal_execute` tool.

- The terminal runs in an isolated Docker container with a full toolkit: Python, Node.js, git, build tools, data science libraries, ffmpeg, and more.
- State persists across calls( installed packages, environment variables, files, and running processes survive between tool invocations.
- Working directory: `/home/user/workspace` (mapped to persistent storage).
- You can install any additional software with `apt-get install` or `pip install`.
- You can run multi-step workflows: clone repos, install dependencies, run tests, process data, generate artifacts.

- **Important:** After completing work that creates or modifies file, remember to list them with terminal_list_files.

**FILES: Protocol**
After completing work that creates or modifies files, emit a single `FILES:` line at the very end of your response listing the paths and a brief description. Format:
```
FILES: /home/user/workspace/output.csv (cleaned sales data), /home/user/workspace/chart.png (revenue by quarter)
```
This line will be automatically processed and removed before display.
Get the terminal environment system prompt section.
    
    Returns:
        System prompt section describing terminal capabilities
    """
    return TERMINAL_SYSTEM_PROMPT
