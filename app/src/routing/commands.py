"""Command parser for slash commands.

Commands are processed before any routing or LLM calls.
They return synthetic responses immediately - zero latency.

Available commands:
- /end_convo - Clear conversation state, force reclassification
- /{preset_name} - Pin routing to a specific preset
- /reflect - Trigger manual reflection cycle (Part8)
- /gaps - List capability gaps ranked by priority (Part8)
- /patterns - Show detected patterns (Part8)
- /opinions - Show opinion pairs (Part8)
- /growth - Show operator growth report (Part8)
- /meta - Show store health metrics (Part8)
- /tools - Show tool suggestions from capability gaps (Part8)
"""
from dataclasses import dataclass
from enum import Enum


class CommandAction(Enum):
    """Actions that can be triggered by slash commands."""
    RESET_CACHE = "reset_cache"
    PIN_PRESET = "pin_preset"
    NOOP = "noop"
    # Part8: New commands for reflection and memory system
    REFLECT = "reflect"
    GAPS = "gaps"
    PATTERNS = "patterns"
    OPINIONS = "opinions"
    GROWTH = "growth"
    META = "meta"
    TOOLS = "tools"
    CLEAR_CHAT = "clear_chat"


@dataclass
class CommandResult:
    """Result of parsing a slash command.
    
    Attributes:
        action: The action to take
        preset: For PIN_PRESET, the preset slug to pin to
        response_text: The response to send back to the user
        command_args: Arguments passed to the command (for Part8 commands)
    """
    action: CommandAction
    preset: str | None = None
    response_text: str = ""
    command_args: str = ""


def parse_command(content: str, available_presets: list[str]) -> CommandResult | None:
    """Parse a slash command from message content.
    
    Commands start with / and are processed before any routing.
    
    Args:
        content: Raw message content
        available_presets: List of valid preset slugs
        
    Returns:
        CommandResult if a command was found, None otherwise
        
    Examples:
        >>> parse_command("/end_convo", ["code", "architecture"])
        CommandResult(action=CommandAction.RESET_CACHE, ...)
        
        >>> parse_command("/code", ["code", "architecture"])
        CommandResult(action=CommandAction.PIN_PRESET, preset="code", ...)
        
        >>> parse_command("/gaps 3", ["code", "architecture"])
        CommandResult(action=CommandAction.GAPS, command_args="3", ...)
        
        >>> parse_command("Hello", ["code", "architecture"])
        None
    """
    stripped = content.strip()
    if not stripped.startswith("/"):
        return None

    # Extract command and args (first word after /, rest is args)
    parts = stripped.lstrip("/").split(maxsplit=1)
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    # Part8: Handle reflection/memory commands
    # These return empty response_text - will be filled by CommandHandler
    if cmd == "reflect":
        return CommandResult(
            action=CommandAction.REFLECT,
            response_text="",  # Filled by CommandHandler
            command_args=args,
        )
    
    if cmd == "gaps":
        return CommandResult(
            action=CommandAction.GAPS,
            response_text="",
            command_args=args,
        )
    
    if cmd == "patterns":
        return CommandResult(
            action=CommandAction.PATTERNS,
            response_text="",
            command_args=args,
        )
    
    if cmd == "opinions":
        return CommandResult(
            action=CommandAction.OPINIONS,
            response_text="",
            command_args=args,
        )
    
    if cmd == "growth":
        return CommandResult(
            action=CommandAction.GROWTH,
            response_text="",
            command_args=args,
        )
    
    if cmd == "meta":
        return CommandResult(
            action=CommandAction.META,
            response_text="",
            command_args=args,
        )
    
    if cmd == "tools":
        return CommandResult(
            action=CommandAction.TOOLS,
            response_text="",
            command_args=args,
        )

    # Handle /end_convo - clear cache and force reclassification
    if cmd == "end_convo":
        return CommandResult(
            action=CommandAction.RESET_CACHE,
            response_text="Acknowledged. Categorisation state cleared. Next message will be re-evaluated."
        )

    # Handle /{preset_name} - pin to a specific preset
    if cmd in available_presets:
        return CommandResult(
            action=CommandAction.PIN_PRESET,
            preset=cmd,
            response_text=f"Acknowledged. Routing pinned to preset: {cmd}. Send /end_convo to release."
        )

    # Unknown command - return NOOP with error message
    return CommandResult(
        action=CommandAction.NOOP,
        response_text=f"Negative. Command \"{cmd}\" not recognized.\nAvailable: end_convo, reflect, gaps, patterns, opinions, growth, meta, tools, or a preset name."
    )
