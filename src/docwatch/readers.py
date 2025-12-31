"""
File readers for extracting content from code and documentation files.

Provides safe file reading with:
- Automatic encoding detection (UTF-8 with latin-1 fallback)
- Graceful error handling for missing/inaccessible files
- Memory-efficient partial reading for large files
"""
import logging
from itertools import islice
from pathlib import Path
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

# Exceptions that indicate file access problems (not encoding issues)
_FILE_ACCESS_ERRORS = (FileNotFoundError, PermissionError, IsADirectoryError)

T = TypeVar('T')


def _read_with_fallback(
    path: Path,
    reader: Callable[[object], T],
    default: T,
    encodings: tuple[str, ...] = ('utf-8', 'latin-1'),
) -> T:
    """
    Read a file using a reader function, trying multiple encodings.

    Args:
        path: Path to the file
        reader: Function that takes a file handle and returns the result
        default: Value to return if file can't be read
        encodings: Tuple of encodings to try in order

    Returns:
        Result from reader function, or default if file can't be read
    """
    for i, encoding in enumerate(encodings):
        try:
            with path.open('r', encoding=encoding) as f:
                return reader(f)
        except UnicodeDecodeError:
            if i < len(encodings) - 1:
                logger.debug(
                    "%s decode failed for %s, trying %s",
                    encoding, path, encodings[i + 1]
                )
                continue
            # Last encoding failed - shouldn't happen with latin-1
            logger.warning("All encodings failed for %s", path)
            return default
        except _FILE_ACCESS_ERRORS as e:
            logger.warning("%s: %s", type(e).__name__, path)
            return default

    return default


def read_file_safe(filepath: Path | str) -> Optional[str]:
    """
    Read a file and return its contents.

    Handles encoding issues gracefully by trying UTF-8 first,
    then falling back to latin-1 (which accepts any byte sequence).

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        File contents as string, or None if file can't be read
    """
    return _read_with_fallback(
        path=Path(filepath),
        reader=lambda f: f.read(),
        default=None,
    )


def read_file_lines(filepath: Path | str) -> list[tuple[int, str]]:
    """
    Read a file and return a list of (line_number, line_content) tuples.

    Line numbers are 1-indexed for human readability.

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        List of (line_number, line_content) tuples, or empty list if unreadable
    """
    content = read_file_safe(filepath)

    if content is None:
        return []

    return [(line_num, line) for line_num, line in enumerate(content.splitlines(), start=1)]


def get_file_preview(
    filepath: Path | str,
    max_lines: int = 10,
) -> list[tuple[int, str]]:
    """
    Read just the first N lines of a file.

    Memory-efficient: only reads the requested lines, not the entire file.

    Args:
        filepath: Path to file (string or Path object)
        max_lines: Maximum number of lines to read (default 10)

    Returns:
        List of (line_number, line_content) tuples
    """
    def read_lines(f):
        # islice() is lazy - only reads max_lines from the file iterator
        lines = list(islice(f, max_lines))
        return [(i, line.rstrip('\n\r')) for i, line in enumerate(lines, start=1)]

    return _read_with_fallback(
        path=Path(filepath),
        reader=read_lines,
        default=[],
    )
