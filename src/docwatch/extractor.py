"""
Extraction pipeline for parsing code and documentation files.

This module converts raw files into structured models (CodeFile, DocFile).
"""
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from docwatch.models import (
    Language, DocFormat, EntityType, ReferenceType,
    Location, CodeEntity, DocReference, CodeFile, DocFile
)
from docwatch.readers import read_file_safe
from docwatch.scanner import categorize_files
from docwatch.extractors import python_ast, js_extractor, notebook_extractor
from docwatch.extractors import markdown_extractor, rst_extractor, asciidoc_extractor


def extract_code_file(filepath: Path) -> Optional[CodeFile]:
    """
    Parse a code file and extract all entities.

    Args:
        filepath: Path to the code file (including .ipynb notebooks)

    Returns:
        CodeFile with entities, or None if unreadable
    """
    # Handle Jupyter notebooks specially (they're JSON, not plain text)
    if filepath.suffix.lower() == '.ipynb':
        return _extract_notebook(filepath)

    content = read_file_safe(filepath)
    if content is None:
        logger.warning("Failed to read code file: %s", filepath)
        return None

    language = Language.from_extension(filepath.suffix)

    # Python: Use AST-based extraction for accuracy
    if language == Language.PYTHON:
        entities, imports = python_ast.extract_from_source(content, filepath)
        return CodeFile(
            path=filepath,
            language=language,
            entities=entities,
            imports=imports,
        )

    # JavaScript/TypeScript: Use regex extraction
    if language in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        return _extract_js_code_file(filepath, content, language)

    # No extractor available, return file with no entities
    return CodeFile(path=filepath, language=language)


def _extract_js_code_file(
    filepath: Path,
    content: str,
    language: Language
) -> CodeFile:
    """Extract entities from JavaScript/TypeScript files using regex."""
    function_names = js_extractor.extract_function_names(content)
    class_names = js_extractor.extract_class_names(content)
    imports = js_extractor.extract_imports(content)

    entities = []
    lines = content.splitlines()

    for name in function_names:
        line_num = _find_definition_line(lines, name, "function")
        if line_num:
            entities.append(CodeEntity(
                name=name,
                entity_type=EntityType.FUNCTION,
                location=Location(file=filepath, line_start=line_num),
            ))

    for name in class_names:
        line_num = _find_definition_line(lines, name, "class")
        if line_num:
            entities.append(CodeEntity(
                name=name,
                entity_type=EntityType.CLASS,
                location=Location(file=filepath, line_start=line_num),
            ))

    return CodeFile(
        path=filepath,
        language=language,
        entities=entities,
        imports=imports,
    )


def _extract_notebook(filepath: Path) -> Optional[CodeFile]:
    """Extract entities from a Jupyter notebook."""
    entities, imports = notebook_extractor.extract_from_notebook(filepath)

    return CodeFile(
        path=filepath,
        language=Language.PYTHON,  # Notebooks are Python
        entities=entities,
        imports=imports,
    )


def extract_doc_file(filepath: Path) -> Optional[DocFile]:
    """
    Parse a documentation file and extract all references.

    Args:
        filepath: Path to the documentation file

    Returns:
        DocFile with references, or None if unreadable
    """
    content = read_file_safe(filepath)
    if content is None:
        logger.warning("Failed to read doc file: %s", filepath)
        return None

    doc_format = DocFormat.from_extension(filepath.suffix)

    # Select extractor based on format
    if doc_format == DocFormat.MARKDOWN:
        extractor = markdown_extractor
    elif doc_format == DocFormat.RST:
        extractor = rst_extractor
    elif doc_format == DocFormat.ASCIIDOC:
        extractor = asciidoc_extractor
    else:
        # No extractor available
        return DocFile(path=filepath, format=doc_format)

    # Extract raw data
    headers = extractor.extract_headers(content)
    code_blocks = extractor.extract_code_blocks(content)
    inline_refs = extractor.extract_inline_code(content)
    links = extractor.extract_links(content)

    # Build references
    references = []

    # Add inline code references with locations
    for ref_text in inline_refs:
        line_num = _find_reference_line(content, ref_text)
        references.append(DocReference(
            text=ref_text,
            location=Location(file=filepath, line_start=line_num or 1),
            reference_type=ReferenceType.INLINE_CODE,
        ))

    # Add code block identifiers (weaker form of documentation)
    if doc_format == DocFormat.MARKDOWN:
        code_block_ids = markdown_extractor.extract_code_block_identifiers(content)
        for ref_text in code_block_ids:
            # Skip if already captured as inline code
            if ref_text not in inline_refs:
                line_num = _find_reference_line(content, ref_text)
                references.append(DocReference(
                    text=ref_text,
                    location=Location(file=filepath, line_start=line_num or 1),
                    reference_type=ReferenceType.CODE_BLOCK,
                ))

    # Determine title from first header
    title = headers[0]["text"] if headers else None

    return DocFile(
        path=filepath,
        format=doc_format,
        title=title,
        references=references,
        headers=headers,
    )


def process_directory(
    directory: Path,
    ignore_dirs: Optional[set] = None
) -> tuple[list[CodeFile], list[DocFile]]:
    """
    Process all files in a directory.

    Args:
        directory: Path to directory
        ignore_dirs: Directory names to skip

    Returns:
        Tuple of (code_files, doc_files)
    """
    categorized = categorize_files(directory, ignore_dirs=ignore_dirs)

    code_files = []
    for filepath in categorized["code"]:
        code_file = extract_code_file(filepath)
        if code_file is not None:
            code_files.append(code_file)

    doc_files = []
    for filepath in categorized["docs"]:
        doc_file = extract_doc_file(filepath)
        if doc_file is not None:
            doc_files.append(doc_file)

    return code_files, doc_files


def _find_definition_line(lines: list[str], name: str, keyword: str) -> Optional[int]:
    """Find the line number where a definition occurs."""
    import re
    pattern = rf"\b{keyword}\s+{re.escape(name)}\b"

    for i, line in enumerate(lines, start=1):
        if re.search(pattern, line):
            return i
    return None


def _find_reference_line(content: str, ref_text: str) -> Optional[int]:
    """Find the first line where a reference occurs."""
    for i, line in enumerate(content.splitlines(), start=1):
        if ref_text in line:
            return i
    return None
