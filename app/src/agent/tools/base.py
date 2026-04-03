"""Base classes for tool observations.

Provides TextObservation, which correctly wires to_llm_content
from the subclass's visualize property.

Background: The SDK's ObservationEvent.to_llm_message() calls
observation.to_llm_content, which in the base Observation class
reads self.content (a list[TextContent | ImageContent] defaulting
to []). Custom Observations store results in named fields (result,
output, message) and override visualize — but not to_llm_content.
This means the LLM receives empty tool results while the TUI looks
correct.

TextObservation fixes this by overriding to_llm_content to read
from visualize.plain, so Observation subclasses only need to
implement visualize correctly.
"""
from __future__ import annotations

from rich.text import Text
from openhands.sdk.llm import TextContent
from openhands.sdk.tool.tool import Observation


class TextObservation(Observation):
    """Observation base that routes to_llm_content from visualize.plain.

    Subclasses that override visualize with custom logic are unaffected —
    Python MRO picks their override first. Subclasses that don't override
    visualize fall through to this implementation, which reads directly from
    self.content to avoid the circular dependency:
      Observation.visualize → self.to_llm_content → self.visualize → ∞
    """

    @property
    def visualize(self) -> Text:
        text_str = "".join(
            item.text for item in self.content if hasattr(item, "text")
        )
        result = Text()
        result.append(text_str if text_str.strip() else "[no text content]")
        return result

    @property
    def to_llm_content(self):
        text = self.visualize.plain
        return [TextContent(text=text)] if text.strip() else []
