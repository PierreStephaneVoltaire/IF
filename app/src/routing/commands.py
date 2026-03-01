"""Command parser for slash commands.

Commands are processed before any routing or LLM calls.
They return synthetic responses immediately - zero latency.

Available commands:
- /end_convo - Clear conversation state, force reclassification
- /{preset_name} - Pin routing to a specific preset
"""
from dataclasses import dataclass
from enum import Enum


class CommandAction(Enum):
    """Actions that can be triggered by slash commands."""
    RESET_CACHE = "reset_cache"
    PIN_PRESET = "pin_preset"
    NOOP = "noop"


@dataclass
class CommandResult:
    """Result of parsing a slash command.
    
    Attributes:
        action: The action to take
        preset: For PIN_PRESET, the preset slug to pin to
        response_text: The response to send back to the user
    """
    action: CommandAction
    preset: str | None = None
    response_text: str = ""


def parse_command(content: str, available_presets: list[str]) -> CommandResult | None:
    """Parse a slash command from message content.
    
    Commands start with / and are processed before any routing.
    
    Args:
        content: Raw message content
        available_presets: List of valid preset slugs
        
    Returns:
        CommandResult if a command was found, None otherwise
        
    Examples:
        >>> parse_command("/end_convo", ["coding", "architecture"])
        CommandResult(action=CommandAction.RESET_CACHE, ...)
        
        >>> parse_command("/coding", ["coding", "architecture"])
        CommandResult(action=CommandAction.PIN_PRESET, preset="coding", ...)
        
        >>> parse_command("Hello", ["coding", "architecture"])
        None
    """
    stripped = content.strip()
    if not stripped.startswith("/"):
        return None

    # Extract command (first word after /)
    cmd = stripped.lstrip("/").lower().split()[0]

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
        response_text=f"Negative. Preset \"{cmd}\" not recognized.\nAvailable: {', '.join(sorted(available_presets))}."
    )
