"""
File readers for extracting content from code and documentation files.
"""
import logging
from itertools import islice
from pathlib import Path

logger = logging.getLogger(__name__)


def read_file_safe(filepath):
    """
    Read a file and return its contents.
    Handle encoding issues gracefully.
    Return None if file can't be read.

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        str: File contents, or None if file can't be read
    """
    path = Path(filepath)

    # First attempt: UTF-8 (the most common encoding)
    try:
        with path.open('r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        logger.debug("UTF-8 decode failed for %s, trying latin-1", path)
    except FileNotFoundError:
        logger.warning("File not found: %s", path)
        return None
    except PermissionError:
        logger.warning("Permission denied: %s", path)
        return None
    except IsADirectoryError:
        logger.warning("Path is a directory, not a file: %s", path)
        return None

    # Fallback: latin-1 (can read any byte sequence, never fails)
    try:
        with path.open('r', encoding='latin-1') as f:
            return f.read()
    except FileNotFoundError:
        logger.warning("File not found: %s", path)
        return None
    except PermissionError:
        logger.warning("Permission denied: %s", path)
        return None
    except IsADirectoryError:
        logger.warning("Path is a directory, not a file: %s", path)
        return None


def read_file_lines(filepath):
    """
    Read a file and return a list of (line_number, line_content) tuples.
    Preserve line numbers for later reference.

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        list: List of (line_number, line_content) tuples, or empty list if unreadable
    """
    content = read_file_safe(filepath)

    if content is None:
        return []

    # enumerate() gives us (index, value) pairs
    # start=1 makes line numbers human-readable (1-indexed, not 0-indexed)
    return [(line_num, line) for line_num, line in enumerate(content.splitlines(), start=1)]


def get_file_preview(filepath, max_lines=10):
    """
    Read just the first N lines of a file.
    Useful for large files - only reads what's needed.

    Args:
        filepath: Path to file (string or Path object)
        max_lines: Maximum number of lines to read (default 10)

    Returns:
        list: List of (line_number, line_content) tuples
    """
    path = Path(filepath)

    try:
        with path.open('r', encoding='utf-8') as f:
            # File objects are iterators - they yield one line at a time
            # islice(iterator, n) takes only the first n items WITHOUT reading the rest
            lines = list(islice(f, max_lines))
    except UnicodeDecodeError:
        logger.debug("UTF-8 decode failed for %s, trying latin-1", path)
        try:
            with path.open('r', encoding='latin-1') as f:
                lines = list(islice(f, max_lines))
        except FileNotFoundError:
            logger.warning("File not found: %s", path)
            return []
        except PermissionError:
            logger.warning("Permission denied: %s", path)
            return []
        except IsADirectoryError:
            logger.warning("Path is a directory: %s", path)
            return []
    except FileNotFoundError:
        logger.warning("File not found: %s", path)
        return []
    except PermissionError:
        logger.warning("Permission denied: %s", path)
        return []
    except IsADirectoryError:
        logger.warning("Path is a directory: %s", path)
        return []

    # Strip trailing newlines and add line numbers
    return [(i, line.rstrip('\n\r')) for i, line in enumerate(lines, start=1)]
