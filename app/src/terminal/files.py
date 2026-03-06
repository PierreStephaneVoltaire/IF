"""FILES: line stripping for agent responses.

The agent emits a FILES: line at the end of its response to indicate
which files were created/modified during the response. This module
provides utilities to strip this line before the response reaches
the client.

Format: FILES: /path/to/file.py (description), /path/to/other.py (description)

This line is stripped from the response to prevent it from entering
chat history / context window, while the file references are captured
for attachment handling.
"""
from __future__ import annotations
import re
import logging
from dataclasses import dataclass
from typing import List, Tuple

logger = logging.getLogger(__name__)


@dataclass
class FileRef:
    """Reference to a file mentioned in FILES: line.
    
    Attributes:
        path: Absolute or relative path to the file
        description: Human-readable description of the file
    """
    path: str
    description: str


# Regex to find the FILES: line (must be at start of a line)
_FILES_RE = re.compile(r"^FILES:\s*(.+)$", re.MULTILINE)

# Regex to parse individual file entries: path (description)
_ENTRY_RE = re.compile(r"(\S+)\s*\(([^)]+)\)")


def strip_files_line(text: str) -> Tuple[str, List[FileRef]]:
    """Remove FILES: line from text and extract file references.
    
    The FILES: line format is:
        FILES: /path/to/file.py (description), /path/to/other.py (description)
    
    Args:
        text: Response text that may contain a FILES: line
        
    Returns:
        Tuple of (cleaned_text, file_refs) where:
        - cleaned_text: Original text with FILES: line removed
        - file_refs: List of FileRef objects extracted from the line
    """
    m = _FILES_RE.search(text)
    if not m:
        return text, []
    
    # Extract file references from the matched line
    files_content = m.group(1)
    refs = []
    for entry_match in _ENTRY_RE.finditer(files_content):
        path = entry_match.group(1)
        description = entry_match.group(2).strip()
        refs.append(FileRef(path=path, description=description))
    
    # Remove the FILES: line from the text
    # Preserve text before and after the match
    cleaned = text[:m.start()].rstrip("\n") + text[m.end():]
    
    return cleaned.rstrip("\n"), refs


class FilesStripBuffer:
    """Buffer for stripping FILES: line from streaming responses.
    
    The FILES: line is always the last line of the response. This buffer
    holds back the tail of the stream to ensure the FILES: line is
    completely captured before stripping.
    
    Usage:
        buf = FilesStripBuffer()
        async for chunk in stream:
            text = extract_text_delta(chunk)
            if text:
                emit = buf.feed(text)
                if emit:
                    yield make_chunk(emit)
        remaining, refs = buf.finalize()
        if remaining:
            yield make_chunk(remaining)
        # Handle refs as needed
    """
    
    # Number of characters to hold back in case FILES: spans chunk boundary
    TAIL_SIZE = 500
    
    def __init__(self):
        """Initialize the buffer."""
        self._tail = ""
    
    def feed(self, chunk: str) -> str:
        """Feed a text chunk to the buffer.
        
        Holds back the last TAIL_SIZE characters to ensure the FILES:
        line is completely captured before emitting.
        
        Args:
            chunk: Text chunk from the stream
            
        Returns:
            Text that is safe to emit (may be empty string)
        """
        combined = self._tail + chunk
        
        # If combined is small, just keep buffering
        if len(combined) <= self.TAIL_SIZE:
            self._tail = combined
            return ""
        
        # Emit everything except the tail
        emit = combined[:-self.TAIL_SIZE]
        self._tail = combined[-self.TAIL_SIZE:]
        return emit
    
    def finalize(self) -> Tuple[str, List[FileRef]]:
        """Finalize the buffer and extract any FILES: line.
        
        Call this after the stream is exhausted to get the remaining
        text (with FILES: line stripped) and the file references.
        
        Returns:
            Tuple of (remaining_text, file_refs)
        """
        cleaned, refs = strip_files_line(self._tail)
        self._tail = ""
        return cleaned, refs
    
    def reset(self) -> None:
        """Reset the buffer to initial state."""
        self._tail = ""


def log_file_refs(conversation_id: str, refs: List[FileRef]) -> None:
    """Log extracted file references for debugging.
    
    Args:
        conversation_id: The conversation/chat ID
        refs: List of file references to log
    """
    if refs:
        paths = [r.path for r in refs]
        logger.info(f"[FILES] {conversation_id}: {paths}")
        for ref in refs:
            logger.debug(f"[FILES]   - {ref.path}: {ref.description}")
