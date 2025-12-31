"""
Extract structured information from reStructuredText (RST) files.
"""
from docwatch.constants import DEFAULT_CODE_BLOCK_LANGUAGE, RST_UNDERLINE_CHARS
from docwatch.extractors.patterns import (
    RST_CODE_BLOCK_DIRECTIVE,
    RST_INLINE_CODE,
    RST_INLINE_LINK,
    RST_REFERENCE_DEF,
)
from docwatch.models import CodeBlockInfo, HeaderInfo, LinkInfo

__all__ = [
    "extract_headers",
    "extract_code_blocks",
    "extract_inline_code",
    "extract_links",
]


def extract_headers(content: str) -> list[HeaderInfo]:
    """
    Extract RST headers with their levels.

    RST headers are text lines followed by underlines of =, -, ~, ^, ", etc.
    The underline must be at least as long as the text.

    Args:
        content: RST content as a string

    Returns:
        list: [{'level': 1, 'text': 'Title', 'line': 1}, ...]
    """
    headers = []
    lines = content.splitlines()

    # RST uses underline characters to define headers
    # The first style encountered becomes level 1, second becomes level 2, etc.
    seen_styles = []  # Track order of underline styles

    for i, line in enumerate(lines):
        # Check if next line exists and is an underline
        if i + 1 < len(lines):
            next_line = lines[i + 1]

            # Check if next line is a valid underline
            if (len(next_line) >= len(line.rstrip()) and
                len(line.strip()) > 0 and
                len(next_line) > 0 and
                next_line[0] in RST_UNDERLINE_CHARS and
                all(c == next_line[0] for c in next_line.rstrip())):

                underline_char = next_line[0]

                # Determine level based on order seen
                if underline_char not in seen_styles:
                    seen_styles.append(underline_char)

                level = seen_styles.index(underline_char) + 1

                headers.append({
                    'level': level,
                    'text': line.strip(),
                    'line': i + 1  # 1-indexed
                })

    return headers


def extract_code_blocks(content: str) -> list[CodeBlockInfo]:
    """
    Extract code blocks from RST.

    RST has multiple code block syntaxes:
    - Indented blocks after ::
    - .. code-block:: language directive

    Args:
        content: RST content as a string

    Returns:
        list: [{'language': 'python', 'code': '...', 'start_line': 10, 'end_line': 15}, ...]
    """
    blocks = []
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for .. code-block:: directive
        match = RST_CODE_BLOCK_DIRECTIVE.match(line)
        if match:
            language = match.group(1) or DEFAULT_CODE_BLOCK_LANGUAGE
            start_line = i + 1

            # Skip blank lines and options
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith('   :')):
                i += 1

            # Collect indented code
            code_lines = []
            while i < len(lines) and (lines[i].startswith('   ') or not lines[i].strip()):
                if lines[i].strip():  # Only add non-empty lines
                    code_lines.append(lines[i][3:])  # Remove 3-space indent
                elif code_lines:  # Preserve blank lines within code
                    code_lines.append('')
                i += 1

            if code_lines:
                blocks.append({
                    'language': language,
                    'code': '\n'.join(code_lines).strip(),
                    'start_line': start_line,
                    'end_line': i
                })
            continue

        # Check for :: at end of paragraph (literal block)
        if line.rstrip().endswith('::'):
            start_line = i + 1

            # Skip blank line after ::
            i += 1
            while i < len(lines) and not lines[i].strip():
                i += 1

            # Collect indented code
            code_lines = []
            while i < len(lines) and (lines[i].startswith('   ') or not lines[i].strip()):
                if lines[i].strip():
                    code_lines.append(lines[i][3:])
                elif code_lines:
                    code_lines.append('')
                i += 1

            if code_lines:
                blocks.append({
                    'language': DEFAULT_CODE_BLOCK_LANGUAGE,
                    'code': '\n'.join(code_lines).strip(),
                    'start_line': start_line,
                    'end_line': i
                })
            continue

        i += 1

    return blocks


def extract_inline_code(content: str) -> list[str]:
    """
    Extract inline code references from RST.
    RST uses double backticks: ``code``

    Args:
        content: RST content as a string

    Returns:
        list: Unique inline code strings found
    """
    matches = RST_INLINE_CODE.findall(content)

    # Return unique values
    seen = set()
    unique = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique.append(match)

    return unique


def extract_links(content: str) -> list[LinkInfo]:
    """
    Extract links from RST.

    RST link formats:
    - `text <url>`_  (inline)
    - `text`_  (reference, with .. _text: url elsewhere)

    Args:
        content: RST content as a string

    Returns:
        list: [{'text': 'link text', 'url': 'https://...', 'line': 5}, ...]
    """
    links = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Inline links: `text <url>`_
        for match in RST_INLINE_LINK.finditer(line):
            links.append({
                'text': match.group(1).strip(),
                'url': match.group(2),
                'line': line_num
            })

    # Also collect reference definitions: .. _name: url
    for line_num, line in enumerate(content.splitlines(), start=1):
        match = RST_REFERENCE_DEF.match(line)
        if match:
            links.append({
                'text': match.group(1).strip(),
                'url': match.group(2).strip(),
                'line': line_num
            })

    return links
