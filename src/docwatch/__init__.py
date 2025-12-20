"""
docwatch - File scanner and content extractor for analyzing codebases.
"""

__version__ = "0.1.0"

from docwatch.scanner import categorize_files, get_directory_stats
from docwatch.extractor import (
    CodeFile,
    DocFile,
    extract_code_info,
    extract_doc_info,
    process_directory,
)
from docwatch.readers import read_file_safe, read_file_lines, get_file_preview

__all__ = [
    # Version
    "__version__",
    # Scanner
    "categorize_files",
    "get_directory_stats",
    # Extractor
    "CodeFile",
    "DocFile",
    "extract_code_info",
    "extract_doc_info",
    "process_directory",
    # Readers
    "read_file_safe",
    "read_file_lines",
    "get_file_preview",
]
