"""Message translation for different platforms.

Translators convert platform-specific message formats into the standard
ChatCompletionRequest format used by the agent pipeline.
"""

from channels.translators.discord_translator import translate_discord_batch
from channels.translators.openwebui_translator import translate_openwebui_batch

__all__ = [
    "translate_discord_batch",
    "translate_openwebui_batch",
]
