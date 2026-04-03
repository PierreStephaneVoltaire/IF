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

from openhands.sdk.llm import TextContent
from openhands.sdk.tool.tool import Observation


class TextObservation(Observation):
    """Observation base that routes to_llm_content from visualize.plain."""

    @property
    def to_llm_content(self):
        text = self.visualize.plain
        return [TextContent(text=text)] if text.strip() else []
