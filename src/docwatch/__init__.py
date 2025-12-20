"""
docwatch - Documentation decay detection for codebases.

Scans code and documentation files, builds a relationship graph,
and identifies coverage gaps and stale references.
"""

__version__ = "0.1.0"

# Models
from docwatch.models import (
    Language,
    DocFormat,
    EntityType,
    ReferenceType,
    LinkType,
    Location,
    CodeEntity,
    DocReference,
    CodeDocLink,
    CodeFile,
    DocFile,
)

# Core functionality
from docwatch.scanner import categorize_files, get_directory_stats
from docwatch.extractor import extract_code_file, extract_doc_file, process_directory
from docwatch.graph import DocumentationGraph
from docwatch.analyzer import DocumentationAnalyzer, CoverageStats

# File readers
from docwatch.readers import read_file_safe, read_file_lines, get_file_preview

__all__ = [
    # Version
    "__version__",
    # Enums
    "Language",
    "DocFormat",
    "EntityType",
    "ReferenceType",
    "LinkType",
    # Models
    "Location",
    "CodeEntity",
    "DocReference",
    "CodeDocLink",
    "CodeFile",
    "DocFile",
    # Scanner
    "categorize_files",
    "get_directory_stats",
    # Extractor
    "extract_code_file",
    "extract_doc_file",
    "process_directory",
    # Graph
    "DocumentationGraph",
    # Analyzer
    "DocumentationAnalyzer",
    "CoverageStats",
    # Readers
    "read_file_safe",
    "read_file_lines",
    "get_file_preview",
]
