"""Response chunking for platform delivery.

Splits long responses into chunks for platform delivery.
Priority: paragraph break > sentence break > newline > space > hard cut.
Preserves code blocks intact when possible.
"""
from __future__ import annotations
from typing import List

from config import CHANNEL_MAX_CHUNK_CHARS


def chunk_response(
    text: str,
    max_chars: int | None = None,
) -> List[str]:
    """Split text into chunks respecting platform character limits.
    
    Tries to split at natural boundaries in priority order:
    1. Paragraph break (double newline)
    2. Sentence end with newline
    3. Sentence end with space
    4. Newline
    5. Space
    6. Hard cut (last resort)
    
    Also tries to preserve code blocks intact when possible.
    
    Args:
        text: Text to chunk
        max_chars: Maximum characters per chunk (defaults to config)
        
    Returns:
        List of text chunks, each <= max_chars
    """
    if max_chars is None:
        max_chars = CHANNEL_MAX_CHUNK_CHARS

    if len(text) <= max_chars:
        return [text]

    chunks: List[str] = []
    remaining = text

    while remaining:
        if len(remaining) <= max_chars:
            chunks.append(remaining)
            break

        # Find the best split point
        cut = _find_split_point(remaining, max_chars)

        chunk = remaining[:cut].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[cut:].lstrip()

    return chunks


def _find_split_point(text: str, max_chars: int) -> int:
    """Find the best split point in text within max_chars.
    
    Args:
        text: Text to find split point in
        max_chars: Maximum position to consider
        
    Returns:
        Position to split at (may be max_chars for hard cut)
    """
    # Check for code block boundaries first
    code_block_split = _find_code_block_split(text, max_chars)
    if code_block_split > 0:
        return code_block_split

    # Try split points in priority order
    delimiters = ["\n\n", ".\n", ". ", "\n", " "]
    
    for delimiter in delimiters:
        pos = text.rfind(delimiter, 0, max_chars)
        # Only use if it's not too early (at least 30% of max)
        if pos > int(max_chars * 0.3):
            return pos + len(delimiter)

    # Hard cut as last resort
    return max_chars


def _find_code_block_split(text: str, max_chars: int) -> int:
    """Try to find a split point that preserves code blocks.
    
    Looks for the end of a code block before max_chars.
    
    Args:
        text: Text to search
        max_chars: Maximum position to consider
        
    Returns:
        Position after code block end, or 0 if no good split found
    """
    # Look for code block end markers (```)
    # We want to find ``` followed by content, then another ```
    # And split after the closing ```
    
    search_region = text[:max_chars]
    
    # Count code block markers
    marker_count = search_region.count("```")
    
    # If odd number of markers, we're inside a code block
    # Try to find the closing marker
    if marker_count % 2 == 1:
        # Look for the next closing marker after max_chars
        next_marker = text.find("```", max_chars)
        if next_marker != -1 and next_marker < max_chars + 500:
            # Include content up to and including the closing marker
            end_pos = next_marker + 3
            return end_pos
    
    # Check if we can split right after a code block ends
    last_block_end = search_region.rfind("```")
    if last_block_end > int(max_chars * 0.5):
        # Make sure it's a closing marker (odd number up to that point)
        markers_before = text[:last_block_end].count("```")
        if markers_before % 2 == 1:
            # This is a closing marker
            return last_block_end + 3
    
    return 0


def estimate_chunks(text: str, max_chars: int | None = None) -> int:
    """Estimate the number of chunks a text will be split into.
    
    Args:
        text: Text to estimate
        max_chars: Maximum characters per chunk
        
    Returns:
        Estimated number of chunks
    """
    return len(chunk_response(text, max_chars))
