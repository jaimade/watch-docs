"""
Extractors for code and documentation files.

Code extractors:
- python_extractor: Python source files (regex-based, lightweight)
- python_ast: Python source files (AST-based, full metadata)
- js_extractor: JavaScript/TypeScript files
- notebook_extractor: Jupyter notebooks (.ipynb)

Documentation extractors:
- markdown_extractor: Markdown files
- rst_extractor: reStructuredText files
- asciidoc_extractor: AsciiDoc files
"""

from docwatch.extractors import python_extractor
from docwatch.extractors import python_ast
from docwatch.extractors import js_extractor
from docwatch.extractors import markdown_extractor
from docwatch.extractors import rst_extractor
from docwatch.extractors import asciidoc_extractor
from docwatch.extractors import notebook_extractor

__all__ = [
    "python_extractor",
    "python_ast",
    "js_extractor",
    "notebook_extractor",
    "markdown_extractor",
    "rst_extractor",
    "asciidoc_extractor",
]
