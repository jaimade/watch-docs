"""
Extractors for code and documentation files.

Code extractors:
- python_extractor: Python source files
- js_extractor: JavaScript/TypeScript files

Documentation extractors:
- markdown_extractor: Markdown files
- rst_extractor: reStructuredText files
- asciidoc_extractor: AsciiDoc files
"""

from docwatch.extractors import python_extractor
from docwatch.extractors import js_extractor
from docwatch.extractors import markdown_extractor
from docwatch.extractors import rst_extractor
from docwatch.extractors import asciidoc_extractor

__all__ = [
    "python_extractor",
    "js_extractor",
    "markdown_extractor",
    "rst_extractor",
    "asciidoc_extractor",
]
