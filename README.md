# docwatch

File scanner and content extractor for analyzing codebases. Categorizes files, extracts structured information from code and documentation.

## Installation

```bash
git clone https://github.com/jaimade/watch-docs.git
cd watch-docs
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

## CLI Usage

```bash
# Basic scan
docwatch /path/to/project

# With detailed statistics
docwatch /path/to/project --stats

# Export to JSON
docwatch /path/to/project --stats --output results.json

# Include normally-ignored directories (.git, node_modules, etc.)
docwatch /path/to/project --no-ignore
```

## API

### Scanner

```python
from docwatch.scanner import categorize_files, get_directory_stats

# Categorize files in a directory
result = categorize_files('/path/to/project')
# {'code': [Path(...), ...], 'docs': [Path(...), ...]}

# Get statistics
stats = get_directory_stats('/path/to/project')
# {'total_files': 42, 'by_category': {...}, 'by_extension': {...}, 'largest_files': [...]}
```

### Extraction Pipeline

```python
from docwatch.extractor import process_directory, extract_code_info, extract_doc_info

# Process entire directory
code_files, doc_files = process_directory('/path/to/project')

# Process single file
from pathlib import Path
code_info = extract_code_info(Path('app.py'))
# CodeFile(path=..., language='python', functions=[...], classes=[...], imports=[...])

doc_info = extract_doc_info(Path('README.md'))
# DocFile(path=..., format='markdown', headers=[...], code_references=[...], links=[...])
```

### File Readers

```python
from docwatch.readers import read_file_safe, read_file_lines, get_file_preview

# Safe reading with encoding fallback
content = read_file_safe('file.py')  # Returns None if unreadable

# Read with line numbers
lines = read_file_lines('file.py')  # [(1, 'line1'), (2, 'line2'), ...]

# Preview first N lines (memory efficient for large files)
preview = get_file_preview('large.log', max_lines=10)
```

### Code Extractors

```python
from docwatch.extractors import python_extractor, js_extractor

# Python
python_extractor.extract_function_names(content)  # ['func1', 'func2']
python_extractor.extract_class_names(content)     # ['MyClass']
python_extractor.extract_imports(content)         # ['os', 'pathlib']
python_extractor.extract_docstrings(content)      # {'func1': 'Docstring...'}

# JavaScript/TypeScript
js_extractor.extract_function_names(content)  # ['fetchData', 'handleClick']
js_extractor.extract_class_names(content)     # ['Component']
js_extractor.extract_imports(content)         # ['react', 'axios']
js_extractor.extract_exports(content)         # ['default', 'helper']
```

### Documentation Extractors

```python
from docwatch.extractors import markdown_extractor, rst_extractor, asciidoc_extractor

# All extractors share the same interface
extractor = markdown_extractor  # or rst_extractor, asciidoc_extractor

extractor.extract_headers(content)
# [{'level': 1, 'text': 'Title', 'line': 1}, ...]

extractor.extract_code_blocks(content)
# [{'language': 'python', 'code': '...', 'start_line': 5, 'end_line': 10}, ...]

extractor.extract_inline_code(content)
# ['function_name', 'ClassName', ...]

extractor.extract_links(content)
# [{'text': 'link', 'url': 'https://...', 'line': 15}, ...]
```

## Supported Formats

### Code Files

| Language | Extensions | Extraction |
|----------|------------|------------|
| Python | `.py`, `.pyi` | functions, classes, imports, docstrings |
| JavaScript | `.js`, `.mjs`, `.cjs`, `.jsx` | functions, classes, imports, exports |
| TypeScript | `.ts`, `.tsx` | functions, classes, imports, exports |
| Other | `.go`, `.rs`, `.java`, `.rb`, etc. | detection only |

### Documentation Files

| Format | Extensions | Extraction |
|--------|------------|------------|
| Markdown | `.md`, `.markdown` | headers, code blocks, inline code, links |
| reStructuredText | `.rst` | headers, code blocks, inline code, links |
| AsciiDoc | `.adoc`, `.asciidoc` | headers, code blocks, inline code, links |
| Plain text | `.txt` | detection only |

## Project Structure

```
src/docwatch/
├── __init__.py
├── scanner.py              # File discovery and categorization
├── readers.py              # Safe file reading utilities
├── cli.py                  # Command-line interface
├── extractor.py            # Extraction pipeline and data classes
└── extractors/
    ├── python_extractor.py
    ├── js_extractor.py
    ├── markdown_extractor.py
    ├── rst_extractor.py
    └── asciidoc_extractor.py
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT
