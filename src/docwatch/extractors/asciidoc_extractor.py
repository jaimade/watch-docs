"""
Extract structured information from AsciiDoc files.
"""
import re


def extract_headers(content):
    """
    Extract AsciiDoc headers with their levels.

    AsciiDoc headers use = prefix:
    - = Title (level 1)
    - == Section (level 2)
    - === Subsection (level 3)

    Args:
        content: AsciiDoc content as a string

    Returns:
        list: [{'level': 1, 'text': 'Title', 'line': 1}, ...]
    """
    headers = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        # Match lines starting with 1-6 '=' characters followed by space
        match = re.match(r'^(={1,6})\s+(.+)$', line)
        if match:
            headers.append({
                'level': len(match.group(1)),
                'text': match.group(2).strip(),
                'line': line_num
            })

    return headers


def extract_code_blocks(content):
    """
    Extract code blocks from AsciiDoc.

    AsciiDoc code blocks:
    - [source,language] followed by ---- delimited block
    - ---- delimited blocks (no language specified)

    Args:
        content: AsciiDoc content as a string

    Returns:
        list: [{'language': 'python', 'code': '...', 'start_line': 10, 'end_line': 15}, ...]
    """
    blocks = []
    lines = content.splitlines()
    i = 0

    while i < len(lines):
        line = lines[i]

        # Check for [source,language] attribute
        language = 'text'
        source_match = re.match(r'\[source,?\s*(\w*)\]', line)
        if source_match:
            language = source_match.group(1) or 'text'
            i += 1
            if i >= len(lines):
                break
            line = lines[i]

        # Check for ---- delimiter
        if line.strip() == '----':
            start_line = i + 1

            # Collect code until closing ----
            i += 1
            code_lines = []
            while i < len(lines) and lines[i].strip() != '----':
                code_lines.append(lines[i])
                i += 1

            if code_lines:
                blocks.append({
                    'language': language,
                    'code': '\n'.join(code_lines),
                    'start_line': start_line,
                    'end_line': i + 1
                })

        i += 1

    return blocks


def extract_inline_code(content):
    """
    Extract inline code references from AsciiDoc.
    AsciiDoc uses backticks or + for inline code: `code` or +code+

    Args:
        content: AsciiDoc content as a string

    Returns:
        list: Unique inline code strings found
    """
    matches = []

    # Backtick style: `code`
    matches.extend(re.findall(r'`([^`]+)`', content))

    # Plus style: +code+ (less common)
    matches.extend(re.findall(r'\+([^+]+)\+', content))

    # Return unique values
    seen = set()
    unique = []
    for match in matches:
        if match not in seen:
            seen.add(match)
            unique.append(match)

    return unique


def extract_links(content):
    """
    Extract links from AsciiDoc.

    AsciiDoc link formats:
    - link:url[text]
    - url[text]
    - <<anchor,text>> (cross-references)

    Args:
        content: AsciiDoc content as a string

    Returns:
        list: [{'text': 'link text', 'url': 'https://...', 'line': 5}, ...]
    """
    links = []

    for line_num, line in enumerate(content.splitlines(), start=1):
        # link:url[text] format
        for match in re.finditer(r'link:([^\[]+)\[([^\]]*)\]', line):
            links.append({
                'text': match.group(2) or match.group(1),
                'url': match.group(1),
                'line': line_num
            })

        # http(s)://url[text] format (but not when preceded by 'link:')
        # (?<!link:) is a negative lookbehind - only match if NOT preceded by 'link:'
        for match in re.finditer(r'(?<!link:)(https?://[^\[]+)\[([^\]]*)\]', line):
            links.append({
                'text': match.group(2) or match.group(1),
                'url': match.group(1),
                'line': line_num
            })

    return links
