"""
Coverage calculation for documentation analysis.

This module provides statistics and queries for documentation coverage.
"""
from dataclasses import dataclass
from functools import cached_property

from docwatch.models import CodeFile, DocFile, CodeEntity, DocReference, CodeDocLink


@dataclass
class CoverageStats:
    """Documentation coverage statistics."""
    total_entities: int
    documented_entities: int
    total_references: int
    linked_references: int

    @property
    def undocumented_entities(self) -> int:
        """Number of code entities without documentation."""
        return self.total_entities - self.documented_entities

    @property
    def broken_references(self) -> int:
        """Number of documentation references that don't match any code."""
        return self.total_references - self.linked_references

    @property
    def coverage_percent(self) -> float:
        """Documentation coverage as a percentage (0.0 to 100.0)."""
        if self.total_entities == 0:
            return 0.0
        return (self.documented_entities / self.total_entities) * 100

    def to_dict(self) -> dict:
        return {
            "total_entities": self.total_entities,
            "documented_entities": self.documented_entities,
            "undocumented_entities": self.undocumented_entities,
            "coverage_percent": round(self.coverage_percent, 2),
            "total_references": self.total_references,
            "linked_references": self.linked_references,
            "broken_references": self.broken_references,
        }


class CoverageCalculator:
    """
    Calculates documentation coverage statistics.

    Provides methods to query coverage metrics from analyzed files and links.
    """

    def __init__(
        self,
        code_files: list[CodeFile],
        doc_files: list[DocFile],
        links: list[CodeDocLink],
    ):
        self._code_files = code_files
        self._doc_files = doc_files
        self._links = links

    @cached_property
    def _documented_names(self) -> frozenset[str]:
        """Set of qualified names for all documented entities."""
        return frozenset(link.entity.qualified_name for link in self._links)

    @cached_property
    def _linked_ref_keys(self) -> frozenset[tuple[str, int]]:
        """Set of (file, line) keys for all linked references."""
        return frozenset(
            (str(link.reference.location.file), link.reference.location.line_start)
            for link in self._links
        )

    def get_stats(self) -> CoverageStats:
        """Get overall documentation coverage statistics."""
        total_entities = sum(len(cf.entities) for cf in self._code_files)
        total_refs = sum(len(df.references) for df in self._doc_files)

        return CoverageStats(
            total_entities=total_entities,
            documented_entities=len(self._documented_names),
            total_references=total_refs,
            linked_references=len(self._linked_ref_keys),
        )

    def get_undocumented_entities(self) -> list[CodeEntity]:
        """Get all entities without documentation."""
        undocumented = []
        for code_file in self._code_files:
            for entity in code_file.entities:
                if entity.qualified_name not in self._documented_names:
                    undocumented.append(entity)

        return undocumented

    def get_broken_references(self) -> list[DocReference]:
        """Get all references that don't match any code."""
        broken = []
        for doc_file in self._doc_files:
            for ref in doc_file.references:
                key = (str(ref.location.file), ref.location.line_start)
                if key not in self._linked_ref_keys:
                    broken.append(ref)

        return broken

    def get_coverage_by_file(self) -> dict[str, float]:
        """
        Get documentation coverage percentage for each code file.

        Files with no extractable entities are excluded from the results,
        as they have no entities to document (e.g., empty __init__.py,
        files with only imports, or files that failed to parse).

        Returns:
            Dict mapping file path to coverage percentage (0.0 to 100.0).
            Only includes files that have at least one entity.
        """
        coverage = {}
        for code_file in self._code_files:
            # Skip files with no entities - nothing to document
            if not code_file.entities:
                continue

            documented_count = sum(
                1 for entity in code_file.entities
                if entity.qualified_name in self._documented_names
            )
            percentage = (documented_count / len(code_file.entities)) * 100
            coverage[str(code_file.path)] = round(percentage, 2)

        return coverage
