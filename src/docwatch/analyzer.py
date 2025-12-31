"""
Documentation analysis orchestrator.

This module provides the main DocumentationAnalyzer class that coordinates
the analysis pipeline. It delegates to specialized components:
- ReferenceMatcher: Matches documentation references to code entities
- CoverageCalculator: Computes coverage statistics
- PriorityScorer: Scores documentation issues by priority
- AnalysisSerializer: Handles save/load operations
"""
from pathlib import Path
from typing import Optional

from docwatch.coverage import CoverageStats, CoverageCalculator

# Re-export for backward compatibility
__all__ = ["DocumentationAnalyzer", "CoverageStats"]
from docwatch.graph import DocumentationGraph
from docwatch.extractor import process_directory
from docwatch.matcher import ReferenceMatcher
from docwatch.models import (
    CodeFile, DocFile, CodeEntity, DocReference,
    CodeDocLink, LinkType,
)
from docwatch.scorer import PriorityScorer
from docwatch.serializer import AnalysisSerializer


class DocumentationAnalyzer:
    """
    Analyzes documentation coverage for a codebase.

    This is the main entry point for documentation analysis. It orchestrates
    the parsing, matching, and analysis pipeline.

    Usage:
        analyzer = DocumentationAnalyzer()
        analyzer.analyze_directory("/path/to/project")

        # Get results
        stats = analyzer.get_coverage_stats()
        undocumented = analyzer.get_undocumented_entities()
        broken = analyzer.get_broken_references()
    """

    def __init__(self):
        self.graph = DocumentationGraph()
        self.code_files: list[CodeFile] = []
        self.doc_files: list[DocFile] = []
        self.links: list[CodeDocLink] = []
        self._entity_index: dict[str, list[CodeEntity]] = {}

        # Initialize components with empty state
        self._init_components()

        # Track list lengths for cache invalidation (detects in-place mutations)
        self._cache_lengths: tuple[int, int, int] = (0, 0, 0)

    def analyze_directory(
        self,
        directory: Path,
        ignore_dirs: Optional[set] = None
    ) -> None:
        """
        Analyze all files in a directory.

        Args:
            directory: Path to analyze
            ignore_dirs: Directory names to skip
        """
        # Parse files
        self.code_files, self.doc_files = process_directory(directory, ignore_dirs)

        # Build graph and entity index
        for code_file in self.code_files:
            self.graph.add_code_file(code_file)
            for entity in code_file.entities:
                if entity.name not in self._entity_index:
                    self._entity_index[entity.name] = []
                self._entity_index[entity.name].append(entity)

        for doc_file in self.doc_files:
            self.graph.add_doc_file(doc_file)

        # Initialize components
        self._init_components()

        # Match references to entities
        self._build_links()

    def _init_components(self) -> None:
        """Initialize the analysis components."""
        self._matcher = ReferenceMatcher(self._entity_index)
        self._scorer = PriorityScorer(self._matcher)
        self._coverage = CoverageCalculator(
            self.code_files, self.doc_files, self.links
        )

    def _build_links(self) -> None:
        """Match documentation references to code entities."""
        self.links.clear()

        for doc_file in self.doc_files:
            for ref in doc_file.references:
                matches = self._matcher.match(ref)
                for entity, link_type, confidence in matches:
                    link = CodeDocLink(
                        entity=entity,
                        reference=ref,
                        link_type=link_type,
                        confidence=confidence,
                    )
                    self.links.append(link)
                    self.graph.add_link(link)

        # Reinitialize coverage calculator with updated links
        self._coverage = CoverageCalculator(
            self.code_files, self.doc_files, self.links
        )

    # -------------------------------------------------------------------------
    # Matching Methods (delegate to ReferenceMatcher)
    # -------------------------------------------------------------------------

    def _match_reference(
        self, ref: DocReference
    ) -> list[tuple[CodeEntity, LinkType, float]]:
        """
        Find code entities matching a reference.

        Delegates to ReferenceMatcher.match().
        """
        # Reinitialize matcher if entity index has changed
        if self._matcher._entity_index is not self._entity_index:
            self._matcher = ReferenceMatcher(self._entity_index)
            self._scorer = PriorityScorer(self._matcher)
        return self._matcher.match(ref)

    # -------------------------------------------------------------------------
    # Scoring Methods (delegate to PriorityScorer)
    # -------------------------------------------------------------------------

    def _score_undocumented_entity(self, entity: CodeEntity) -> tuple[float, str]:
        """Score an undocumented code entity. Delegates to PriorityScorer."""
        return self._scorer.score_undocumented_entity(entity)

    def _score_broken_reference(self, ref: DocReference) -> tuple[float, str]:
        """Score a broken documentation reference. Delegates to PriorityScorer."""
        return self._scorer.score_broken_reference(ref)

    # -------------------------------------------------------------------------
    # Coverage Methods (delegate to CoverageCalculator)
    # -------------------------------------------------------------------------

    @property
    def _current_coverage(self) -> CoverageCalculator:
        """Get coverage calculator with current data (uses cached instance if unchanged)."""
        # Check if cached calculator is stale by comparing lengths
        # This catches both list replacement AND in-place mutations (append, extend, etc.)
        current_lengths = (
            len(self.code_files),
            len(self.doc_files),
            len(self.links),
        )
        if current_lengths != self._cache_lengths:
            self._coverage = CoverageCalculator(
                self.code_files, self.doc_files, self.links
            )
            self._cache_lengths = current_lengths
        return self._coverage

    def get_coverage_stats(self) -> CoverageStats:
        """Get documentation coverage statistics."""
        return self._current_coverage.get_stats()

    def get_undocumented_entities(self) -> list[CodeEntity]:
        """Get all entities without documentation."""
        return self._current_coverage.get_undocumented_entities()

    def get_broken_references(self) -> list[DocReference]:
        """Get all references that don't match any code."""
        return self._current_coverage.get_broken_references()

    def get_coverage_by_file(self) -> dict[str, float]:
        """
        Get documentation coverage percentage for each code file.

        Returns:
            Dict mapping file path to coverage percentage (0.0 to 100.0)
        """
        return self._current_coverage.get_coverage_by_file()

    # -------------------------------------------------------------------------
    # Query Methods
    # -------------------------------------------------------------------------

    def get_links_for_entity(self, entity_name: str) -> list[CodeDocLink]:
        """Get all documentation links for an entity."""
        return [link for link in self.links if link.entity.name == entity_name]

    def get_links_for_doc(self, doc_path: Path) -> list[CodeDocLink]:
        """Get all links from a documentation file."""
        path_str = str(doc_path)
        return [
            link for link in self.links
            if str(link.reference.location.file) == path_str
        ]

    def find_documentation_clusters(self) -> list[list[str]]:
        """
        Find groups of related code and documentation files.

        Uses graph connectivity to identify which code files are
        documented together. Useful for understanding documentation structure.

        Returns:
            List of clusters, where each cluster is a list of file paths
            (both code and doc files that are related)
        """
        return self.graph.get_connected_file_clusters()

    # -------------------------------------------------------------------------
    # Priority Issue Methods (delegate to PriorityScorer)
    # -------------------------------------------------------------------------

    def get_priority_issues(self) -> list[dict]:
        """
        Identify the most important documentation issues, sorted by priority.

        Collects all issues (undocumented entities, broken references) and
        assigns a priority score to each. Higher scores = more urgent.

        Returns:
            List of issue dicts, sorted by priority (highest first):
            [
                {
                    "type": "undocumented" | "broken_reference",
                    "priority": float,  # 0.0 to 1.0
                    "entity": {...} | None,
                    "reference": {...} | None,
                    "reason": str  # Why this is high/low priority
                },
                ...
            ]
        """
        issues = []

        # Collect undocumented entities
        for entity in self.get_undocumented_entities():
            priority, reason = self._scorer.score_issue(entity, issue_type="undocumented")
            issues.append({
                "type": "undocumented",
                "priority": priority,
                "entity": entity.to_dict(),
                "reference": None,
                "reason": reason,
            })

        # Collect broken references
        for ref in self.get_broken_references():
            priority, reason = self._scorer.score_issue(ref, issue_type="broken_reference")
            issues.append({
                "type": "broken_reference",
                "priority": priority,
                "entity": None,
                "reference": ref.to_dict(),
                "reason": reason,
            })

        # Sort by priority (highest first)
        issues.sort(key=lambda x: x["priority"], reverse=True)
        return issues

    # -------------------------------------------------------------------------
    # Serialization Methods (delegate to AnalysisSerializer)
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Export full analysis as JSON-serializable dict."""
        return {
            "stats": self.get_coverage_stats().to_dict(),
            "code_files": [cf.to_dict() for cf in self.code_files],
            "doc_files": [df.to_dict() for df in self.doc_files],
            "links": [link.to_dict() for link in self.links],
            "undocumented": [e.to_dict() for e in self.get_undocumented_entities()],
            "broken_references": [r.to_dict() for r in self.get_broken_references()],
        }

    def save(self, filepath: Path) -> None:
        """
        Save the analysis to a JSON file.

        Args:
            filepath: Path to save the JSON file
        """
        AnalysisSerializer.save(self, filepath)

    @classmethod
    def load(
        cls,
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
        return AnalysisSerializer.load(filepath, base_dir, validate_paths)
