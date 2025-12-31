"""
Extract structured information from Markdown files.
"""
import re

from docwatch.constants import (
    DEFAULT_CODE_BLOCK_LANGUAGE,
    JS_ALIASES,
    JS_FILTER,
    MIN_IDENTIFIER_LENGTH,
    PYTHON_ALIASES,
    PYTHON_COMMON_TYPES,
    PYTHON_FILTER,
)
from docwatch.extractors.patterns import (
    MARKDOWN_HEADER,
    MARKDOWN_FENCED_CODE_BLOCK,
    MARKDOWN_INLINE_CODE,
    MARKDOWN_LINK,
    CODE_PYTHON_IMPORT,
    CODE_FUNCTION_CALL,
    CODE_CLASS_NAME,
    CODE_JS_DESTRUCTURE_IMPORT,
    CODE_WORD,
)
from docwatch.models import CodeBlockInfo, HeaderInfo, LinkInfo

__all__ = [
    "extract_headers",
    "extract_code_blocks",
    "extract_inline_code",
    "extract_code_block_identifiers",
    "extract_links",
]


def _get_code_block_lines(content: str) -> set[int]:
    """
    Get set of line numbers that are inside fenced code blocks.
    Used to filter out false positives (e.g., # comments in code).

    Args:
        content: Markdown content as a string

    Returns:
        set: Line numbers that are inside code blocks
    """
    code_lines = set()

    for match in MARKDOWN_FENCED_CODE_BLOCK.finditer(content):
        start_line = content[:match.start()].count('\n') + 1
        end_line = content[:match.end()].count('\n') + 1

        # Add all lines from start to end (inclusive)
        for line_num in range(start_line, end_line + 1):
            code_lines.add(line_num)

    return code_lines


def extract_headers(content: str) -> list[HeaderInfo]:
    """
    Extract all markdown headers with their levels.
    Ignores headers inside fenced code blocks.

    Args:
        content: Markdown content as a string

    Returns:
        list: [{'level': 1, 'text': 'Title', 'line': 1}, ...]
    """
    headers = []
    code_block_lines = _get_code_block_lines(content)

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Skip lines inside code blocks
        if line_num in code_block_lines:
            continue

        match = MARKDOWN_HEADER.match(line)
        if match:
            headers.append({
                'level': len(match.group(1)),  # Count the #'s
                'text': match.group(2).strip(),
                'line': line_num
            })

    return headers


def extract_code_blocks(content: str) -> list[CodeBlockInfo]:
    """
    Extract fenced code blocks with their language.

    Args:
        content: Markdown content as a string

    Returns:
        list: [{'language': 'python', 'code': '...', 'start_line': 10, 'end_line': 15}, ...]
    """
    blocks = []

    for match in MARKDOWN_FENCED_CODE_BLOCK.finditer(content):
        # Calculate line numbers from string positions
        start_pos = match.start()
        end_pos = match.end()

        # Count newlines before this match to get line number
        start_line = content[:start_pos].count('\n') + 1
        end_line = content[:end_pos].count('\n') + 1

        blocks.append({
            'language': match.group(1) or DEFAULT_CODE_BLOCK_LANGUAGE,
            'code': match.group(2),
            'start_line': start_line,
            'end_line': end_line
        })

    return blocks


def extract_inline_code(content: str) -> list[str]:
    """
    Extract inline code references (`like_this`).
    These often reference function/class names.

    Args:
        content: Markdown content as a string

    Returns:
        list: Unique inline code strings found
    """
    matches = MARKDOWN_INLINE_CODE.findall(content)

    # Return unique values, preserving first occurrence order
    seen = set()
    unique = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique.append(match)

    return unique


def extract_code_block_identifiers(content: str) -> list[str]:
    """
    Extract likely code identifiers from fenced code blocks.

    Parses import statements, function calls, and class references
    from Python/JS code blocks. These represent "weak" documentation
    (examples rather than explanatory prose).

    Args:
        content: Markdown content as a string

    Returns:
        list: Unique identifier strings found in code blocks
    """
    identifiers = set()

    # Get all code blocks
    blocks = extract_code_blocks(content)

    for block in blocks:
        code = block['code']
        lang = block['language'].lower()

        # Python imports: from x import y, z  OR  import x
        if lang in PYTHON_ALIASES:
            # from module import name1, name2
            from_imports = re.findall(
                r'from\s+[\w.]+\s+import\s+([^#\n]+)',
                code
            )
            for match in from_imports:
                # Split by comma and clean up
                names = CODE_WORD.findall(match)
                identifiers.update(names)

            # import module  (get the module name)
            direct_imports = CODE_PYTHON_IMPORT.findall(code)
            for match in direct_imports:
                # Get the last part of dotted import
                identifiers.add(match.split('.')[-1])

            # Function/method calls: name(  or name.method(
            calls = CODE_FUNCTION_CALL.findall(code)
            identifiers.update(c for c in calls if c not in PYTHON_FILTER)

            # Class instantiation / type hints: ClassName or name: ClassName
            classes = CODE_CLASS_NAME.findall(code)
            identifiers.update(c for c in classes if c not in PYTHON_COMMON_TYPES)

        # JavaScript/TypeScript
        elif lang in JS_ALIASES:
            # import { name } from 'module'
            js_imports = CODE_JS_DESTRUCTURE_IMPORT.findall(code)
            for match in js_imports:
                names = CODE_WORD.findall(match)
                identifiers.update(names)

            # Function calls
            calls = CODE_FUNCTION_CALL.findall(code)
            identifiers.update(c for c in calls if c not in JS_FILTER)

    # Filter out very short identifiers (likely false positives)
    return [i for i in identifiers if len(i) >= MIN_IDENTIFIER_LENGTH]


def extract_links(content: str) -> list[LinkInfo]:
    """
    Extract markdown links [text](url).

    Args:
        content: Markdown content as a string

    Returns:
        list: [{'text': 'link text', 'url': 'https://...', 'line': 5}, ...]
    """
    links = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        for match in MARKDOWN_LINK.finditer(line):
            links.append({
                'text': match.group(1),
                'url': match.group(2),
                'line': line_num
            })

    return links
