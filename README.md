# docwatch

Documentation decay detection for codebases. Scans code and documentation files, builds a relationship graph, and identifies coverage gaps and stale references.

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

# Extract code and documentation analysis
docwatch /path/to/project --extract

# Export to JSON
docwatch /path/to/project --stats --output results.json

# Include normally-ignored directories (.git, node_modules, etc.)
docwatch /path/to/project --no-ignore
```

### Extraction Output

```
Code Analysis:
  src/main.py
    Functions: main, setup, cleanup
    Classes: Application, Config

Documentation Analysis:
  README.md
    Headers: Installation, Usage, API Reference
    Code references: main, setup, Application

Potential Links Found:
  README.md references: main, setup, Application
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
from pathlib import Path
from docwatch.extractor import process_directory, extract_code_file, extract_doc_file

# Process entire directory
code_files, doc_files = process_directory(Path('/path/to/project'))

# Process single file
code_file = extract_code_file(Path('app.py'))
# CodeFile with entities:
#   code_file.entities  # [CodeEntity(name='main', entity_type=FUNCTION, ...), ...]
#   code_file.language  # Language.PYTHON

doc_file = extract_doc_file(Path('README.md'))
# DocFile with references:
#   doc_file.references  # [DocReference(text='main', reference_type=INLINE_CODE, ...), ...]
#   doc_file.format      # DocFormat.MARKDOWN
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

### Documentation Graph

```python
from docwatch.graph import DocumentationGraph
from docwatch.extractor import extract_code_file, extract_doc_file

# Build a graph from files
graph = DocumentationGraph()
graph.add_code_file(extract_code_file(Path('app.py')))
graph.add_doc_file(extract_doc_file(Path('README.md')))

# Query the graph
list(graph.get_entities())      # ['entity:app.main', 'entity:app.MyClass', ...]
list(graph.get_references())    # ['ref:README.md:5:main', ...]
graph.is_entity_documented('entity:app.main')  # True/False
```

### Documentation Analyzer

```python
from pathlib import Path
from docwatch.analyzer import DocumentationAnalyzer

# Analyze a project
analyzer = DocumentationAnalyzer()
analyzer.analyze_directory(Path('/path/to/project'))

# Get coverage statistics
stats = analyzer.get_coverage_stats()
stats.coverage_percent      # 75.0
stats.undocumented_entities # 5
stats.broken_references     # 2

# Per-file coverage
analyzer.get_coverage_by_file()
# {'src/main.py': 100.0, 'src/utils.py': 50.0, ...}

# Find documentation clusters (related code/docs)
analyzer.find_documentation_clusters()
# [['README.md', 'src/main.py'], ['docs/api.md', 'src/api.py'], ...]

# Get prioritized issues (with typo detection)
issues = analyzer.get_priority_issues()
# [
#   {'type': 'broken_reference', 'priority': 0.9, 'reason': "similar to 'process_data'", ...},
#   {'type': 'undocumented', 'priority': 0.8, 'reason': 'Public class', ...},
# ]

# Export full analysis as JSON
analyzer.to_dict()
```

### Data Models

```python
from docwatch.models import (
    Language, DocFormat, EntityType, ReferenceType, LinkType,
    Location, CodeEntity, DocReference, CodeDocLink, CodeFile, DocFile
)

# All models are frozen dataclasses (immutable, hashable)
entity = CodeEntity(
    name='process_data',
    entity_type=EntityType.FUNCTION,
    location=Location(file=Path('app.py'), line_start=42)
)
entity.qualified_name  # 'app.process_data'

# Serialize to dict for JSON export
entity.to_dict()
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
├── __init__.py             # Public API exports
├── models.py               # Data models (CodeEntity, DocReference, etc.)
├── scanner.py              # File discovery and categorization
├── readers.py              # Safe file reading utilities
├── extractor.py            # Extraction pipeline
├── graph.py                # NetworkX-based relationship graph
├── analyzer.py             # Coverage analysis and issue detection
├── cli.py                  # Command-line interface
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
