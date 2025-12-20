"""
Extraction pipeline for processing code and documentation files.
"""
from dataclasses import dataclass, field
from pathlib import Path

from docwatch.readers import read_file_safe
from docwatch.scanner import categorize_files, CODE_EXTENSIONS, DOC_EXTENSIONS
from docwatch.extractors.python_extractor import (
    extract_function_names,
    extract_class_names,
    extract_imports,
)
from docwatch.extractors import markdown_extractor
from docwatch.extractors import rst_extractor
from docwatch.extractors import asciidoc_extractor


# Map file extensions to language names
EXTENSION_TO_LANGUAGE = {
    '.py': 'python',
    '.pyi': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.jsx': 'javascript',
    '.rb': 'ruby',
    '.go': 'go',
    '.rs': 'rust',
    '.java': 'java',
    '.cpp': 'cpp',
    '.c': 'c',
    '.h': 'c',
    '.hpp': 'cpp',
    '.cs': 'csharp',
    '.php': 'php',
    '.sh': 'shell',
    '.bash': 'shell',
}

# Map doc extensions to format names
EXTENSION_TO_FORMAT = {
    '.md': 'markdown',
    '.markdown': 'markdown',
    '.rst': 'rst',
    '.txt': 'text',
    '.adoc': 'asciidoc',
    '.asciidoc': 'asciidoc',
}


@dataclass
class CodeFile:
    """Extracted information from a code file."""
    path: Path
    language: str
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)


@dataclass
class DocFile:
    """Extracted information from a documentation file."""
    path: Path
    format: str
    headers: list[dict] = field(default_factory=list)
    code_references: list[str] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)


def extract_code_info(filepath: Path) -> CodeFile | None:
    """
    Extract all relevant information from a code file.
    Dispatches to the right extractor based on file extension.

    Args:
        filepath: Path to the code file

    Returns:
        CodeFile with extracted info, or None if file can't be read
    """
    path = Path(filepath)
    content = read_file_safe(path)

    if content is None:
        return None

    # Determine language from extension
    ext = path.suffix.lower()
    language = EXTENSION_TO_LANGUAGE.get(ext, ext.lstrip('.'))

    # Currently only Python has full extraction support
    if language == 'python':
        functions = extract_function_names(content)
        classes = extract_class_names(content)
        imports = extract_imports(content)
    else:
        # For other languages, return empty lists for now
        # TODO: Add extractors for other languages
        functions = []
        classes = []
        imports = []

    return CodeFile(
        path=path,
        language=language,
        functions=functions,
        classes=classes,
        imports=imports,
    )


def extract_doc_info(filepath: Path) -> DocFile | None:
    """
    Extract all relevant information from a documentation file.

    Args:
        filepath: Path to the documentation file

    Returns:
        DocFile with extracted info, or None if file can't be read
    """
    path = Path(filepath)
    content = read_file_safe(path)

    if content is None:
        return None

    # Determine format from extension
    ext = path.suffix.lower()
    doc_format = EXTENSION_TO_FORMAT.get(ext, 'text')

    # Select the right extractor module based on format
    if doc_format == 'markdown':
        extractor = markdown_extractor
    elif doc_format == 'rst':
        extractor = rst_extractor
    elif doc_format == 'asciidoc':
        extractor = asciidoc_extractor
    else:
        # Plain text - no extraction
        return DocFile(
            path=path,
            format=doc_format,
            headers=[],
            code_references=[],
            links=[],
        )

    # Extract using the selected module
    headers = extractor.extract_headers(content)
    code_blocks = extractor.extract_code_blocks(content)
    inline_code = extractor.extract_inline_code(content)
    links = extractor.extract_links(content)

    # Combine code references from blocks and inline
    code_refs = inline_code.copy()
    for block in code_blocks:
        code_refs.append(f"[{block['language']}]")

    return DocFile(
        path=path,
        format=doc_format,
        headers=headers,
        code_references=code_refs,
        links=links,
    )


def process_directory(directory: Path, ignore_dirs=None) -> tuple[list[CodeFile], list[DocFile]]:
    """
    Process all files in a directory.
    Extracts information from all code and documentation files.

    Args:
        directory: Path to directory to process
        ignore_dirs: Set of directory names to ignore (uses defaults if None)

    Returns:
        Tuple of (list of CodeFile, list of DocFile)
    """
    # Use scanner to categorize files
    categorized = categorize_files(directory, ignore_dirs=ignore_dirs)

    code_files = []
    doc_files = []

    # Process code files
    for filepath in categorized['code']:
        code_info = extract_code_info(filepath)
        if code_info is not None:
            code_files.append(code_info)

    # Process documentation files
    for filepath in categorized['docs']:
        doc_info = extract_doc_info(filepath)
        if doc_info is not None:
            doc_files.append(doc_info)

    return code_files, doc_files
