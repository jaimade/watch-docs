"""
Extract structured information from Markdown files.
"""
import re


def _get_code_block_lines(content):
    """
    Get set of line numbers that are inside fenced code blocks.
    Used to filter out false positives (e.g., # comments in code).

    Args:
        content: Markdown content as a string

    Returns:
        set: Line numbers that are inside code blocks
    """
    code_lines = set()
    pattern = r'```(\w*)\n(.*?)\n```'

    for match in re.finditer(pattern, content, re.DOTALL):
        start_line = content[:match.start()].count('\n') + 1
        end_line = content[:match.end()].count('\n') + 1

        # Add all lines from start to end (inclusive)
        for line_num in range(start_line, end_line + 1):
            code_lines.add(line_num)

    return code_lines


def extract_headers(content):
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

        # Match lines starting with 1-6 '#' characters followed by space
        # ^      - start of line
        # (#{1,6}) - capture 1-6 hash symbols
        # \s+    - one or more whitespace
        # (.+)   - capture the header text
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            headers.append({
                'level': len(match.group(1)),  # Count the #'s
                'text': match.group(2).strip(),
                'line': line_num
            })

    return headers


def extract_code_blocks(content):
    """
    Extract fenced code blocks with their language.

    Args:
        content: Markdown content as a string

    Returns:
        list: [{'language': 'python', 'code': '...', 'start_line': 10, 'end_line': 15}, ...]
    """
    blocks = []

    # Pattern breakdown:
    #   ```(\w*)   - opening fence with optional language (captured)
    #   \n         - newline after opening fence
    #   (.*?)      - code content (non-greedy, captured)
    #   \n```      - closing fence
    #
    # Flags:
    #   re.DOTALL  - makes '.' match newlines too (for multi-line code)
    pattern = r'```(\w*)\n(.*?)\n```'

    for match in re.finditer(pattern, content, re.DOTALL):
        # Calculate line numbers from string positions
        start_pos = match.start()
        end_pos = match.end()

        # Count newlines before this match to get line number
        start_line = content[:start_pos].count('\n') + 1
        end_line = content[:end_pos].count('\n') + 1

        blocks.append({
            'language': match.group(1) or 'text',  # Default to 'text' if no language
            'code': match.group(2),
            'start_line': start_line,
            'end_line': end_line
        })

    return blocks


def extract_inline_code(content):
    """
    Extract inline code references (`like_this`).
    These often reference function/class names.

    Args:
        content: Markdown content as a string

    Returns:
        list: Unique inline code strings found
    """
    # Match text between single backticks (but not triple backticks)
    # (?<!`)  - negative lookbehind: not preceded by backtick
    # `       - opening backtick
    # ([^`]+) - one or more non-backtick characters (captured)
    # `       - closing backtick
    # (?!`)   - negative lookahead: not followed by backtick
    pattern = r'(?<!`)`([^`]+)`(?!`)'

    matches = re.findall(pattern, content)

    # Return unique values, preserving first occurrence order
    seen = set()
    unique = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique.append(match)

    return unique


def extract_links(content):
    """
    Extract markdown links [text](url).

    Args:
        content: Markdown content as a string

    Returns:
        list: [{'text': 'link text', 'url': 'https://...', 'line': 5}, ...]
    """
    links = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Pattern: [text](url)
        # \[([^\]]+)\]  - [text] - capture text between brackets
        # \(([^)]+)\)   - (url) - capture url between parentheses
        pattern = r'\[([^\]]+)\]\(([^)]+)\)'

        for match in re.finditer(pattern, line):
            links.append({
                'text': match.group(1),
                'url': match.group(2),
                'line': line_num
            })

    return links
