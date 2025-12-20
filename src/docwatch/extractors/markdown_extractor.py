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


def extract_code_block_identifiers(content):
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
        if lang in ('python', 'py', ''):
            # from module import name1, name2
            from_imports = re.findall(
                r'from\s+[\w.]+\s+import\s+([^#\n]+)',
                code
            )
            for match in from_imports:
                # Split by comma and clean up
                names = re.findall(r'(\w+)', match)
                identifiers.update(names)

            # import module  (get the module name)
            direct_imports = re.findall(r'^import\s+([\w.]+)', code, re.MULTILINE)
            for match in direct_imports:
                # Get the last part of dotted import
                identifiers.add(match.split('.')[-1])

            # Function/method calls: name(  or name.method(
            calls = re.findall(r'\b([A-Za-z_]\w*)\s*\(', code)
            # Filter out common Python builtins/keywords
            builtins = {'print', 'len', 'str', 'int', 'list', 'dict', 'set',
                       'range', 'open', 'type', 'isinstance', 'if', 'for', 'while'}
            identifiers.update(c for c in calls if c not in builtins)

            # Class instantiation / type hints: ClassName or name: ClassName
            classes = re.findall(r'\b([A-Z][A-Za-z0-9_]*)\b', code)
            # Filter out common ones
            common = {'True', 'False', 'None', 'Path', 'Optional', 'List', 'Dict', 'Set'}
            identifiers.update(c for c in classes if c not in common)

        # JavaScript/TypeScript
        elif lang in ('javascript', 'js', 'typescript', 'ts'):
            # import { name } from 'module'
            js_imports = re.findall(r'import\s*\{([^}]+)\}', code)
            for match in js_imports:
                names = re.findall(r'(\w+)', match)
                identifiers.update(names)

            # Function calls
            calls = re.findall(r'\b([A-Za-z_]\w*)\s*\(', code)
            builtins = {'console', 'log', 'require', 'async', 'await', 'function'}
            identifiers.update(c for c in calls if c not in builtins)

    # Filter out very short identifiers (likely false positives)
    return [i for i in identifiers if len(i) >= 3]


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
