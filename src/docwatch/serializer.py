"""
Serialization for documentation analysis.

This module handles saving and loading analysis state to/from JSON files.
Includes path validation to prevent path traversal attacks.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from docwatch.constants import ANALYSIS_FILE_VERSION
from docwatch.models import CodeFile, DocFile, CodeDocLink

if TYPE_CHECKING:
    from docwatch.analyzer import DocumentationAnalyzer


class PathTraversalError(ValueError):
    """Raised when a path in loaded data attempts to escape the base directory."""
    pass


def _validate_path(path_str: str, base_dir: Path) -> Path:
    """
    Validate that a path doesn't escape the base directory.

    Args:
        path_str: Path string from JSON data
        base_dir: Base directory that paths must be relative to

    Returns:
        Validated Path object

    Raises:
        PathTraversalError: If path escapes base directory
    """
    path = Path(path_str)

    # If path is absolute, check it's under base_dir
    # If relative, resolve against base_dir and check
    if path.is_absolute():
        resolved = path.resolve()
    else:
        resolved = (base_dir / path).resolve()

    base_resolved = base_dir.resolve()

    # Check if resolved path is under base directory
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise PathTraversalError(
            f"Path '{path_str}' escapes base directory '{base_dir}'"
        )

    return path


def _validate_paths_in_data(data: dict, base_dir: Path) -> None:
    """
    Recursively validate all file paths in loaded JSON data.

    Args:
        data: Loaded JSON data dictionary
        base_dir: Base directory for path validation

    Raises:
        PathTraversalError: If any path escapes base directory
    """
    # Validate code file paths
    for cf in data.get("code_files", []):
        _validate_path(cf.get("path", ""), base_dir)
        for entity in cf.get("entities", []):
            loc = entity.get("location", {})
            if "file" in loc:
                _validate_path(loc["file"], base_dir)

    # Validate doc file paths
    for df in data.get("doc_files", []):
        _validate_path(df.get("path", ""), base_dir)
        for ref in df.get("references", []):
            loc = ref.get("location", {})
            if "file" in loc:
                _validate_path(loc["file"], base_dir)

    # Validate link paths
    for link in data.get("links", []):
        entity = link.get("entity", {})
        loc = entity.get("location", {})
        if "file" in loc:
            _validate_path(loc["file"], base_dir)

        ref = link.get("reference", {})
        loc = ref.get("location", {})
        if "file" in loc:
            _validate_path(loc["file"], base_dir)


class AnalysisSerializer:
    """
    Handles saving and loading documentation analysis.

    Provides static methods for persisting and restoring
    DocumentationAnalyzer state to/from JSON files.
    """

    @staticmethod
    def save(analyzer: "DocumentationAnalyzer", filepath: Path) -> None:
        """
        Save the analysis to a JSON file.

        Args:
            analyzer: The DocumentationAnalyzer to save
            filepath: Path to save the JSON file
        """
        data = {
            "version": ANALYSIS_FILE_VERSION,
            "created_at": datetime.now().isoformat(),
            "code_files": [cf.to_dict() for cf in analyzer.code_files],
            "doc_files": [df.to_dict() for df in analyzer.doc_files],
            "links": [link.to_dict() for link in analyzer.links],
        }

        filepath = Path(filepath)
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def load(
        filepath: Path,
        base_dir: Optional[Path] = None,
        validate_paths: bool = True,
    ) -> "DocumentationAnalyzer":
        """
        Load an analysis from a JSON file.

        Args:
            filepath: Path to the JSON file
            base_dir: Base directory for path validation (defaults to filepath's parent)
            validate_paths: Whether to validate paths against base_dir (default True)

        Returns:
            DocumentationAnalyzer with restored state

        Raises:
            PathTraversalError: If validate_paths=True and any path escapes base_dir
        """
        # Import here to avoid circular import
        from docwatch.analyzer import DocumentationAnalyzer

        filepath = Path(filepath)
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)

        # Validate all paths before reconstructing objects
        if validate_paths:
            effective_base = base_dir or filepath.parent
            _validate_paths_in_data(data, effective_base)

        analyzer = DocumentationAnalyzer()

        # Reconstruct code files
        analyzer.code_files = [
            CodeFile.from_dict(cf) for cf in data.get("code_files", [])
        ]

        # Reconstruct doc files
        analyzer.doc_files = [
            DocFile.from_dict(df) for df in data.get("doc_files", [])
        ]

        # Reconstruct links
        analyzer.links = [
            CodeDocLink.from_dict(link) for link in data.get("links", [])
        ]

        # Rebuild the graph and entity index
        for code_file in analyzer.code_files:
            analyzer.graph.add_code_file(code_file)
            for entity in code_file.entities:
                if entity.name not in analyzer._entity_index:
                    analyzer._entity_index[entity.name] = []
                analyzer._entity_index[entity.name].append(entity)

        for doc_file in analyzer.doc_files:
            analyzer.graph.add_doc_file(doc_file)

        for link in analyzer.links:
            analyzer.graph.add_link(link)

        # Reinitialize components with loaded data
        analyzer._init_components()

        return analyzer
