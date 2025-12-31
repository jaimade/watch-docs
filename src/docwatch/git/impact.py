"""
Impact analysis for code changes on documentation.

This module analyzes how code changes (detected by tracker.py) affect
documentation that references those code entities.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from docwatch.graph import DocumentationGraph
from docwatch.git.tracker import EntityChange, ChangeType, AnalyzedCommit, ChangeTracker
from docwatch.models import file_path_to_module_path, EntityType, Location
from docwatch.constants import (
    CONFIDENCE_BROKEN_REFERENCE,
    CONFIDENCE_SIGNATURE_CHANGED,
    CONFIDENCE_DOCSTRING_CHANGED,
    CONFIDENCE_UNDOCUMENTED,
)


class ImpactType(Enum):
    """Types of impact a code change can have on documentation."""
    BROKEN_REFERENCE = "broken_reference"      # Entity deleted, docs reference it
    POSSIBLY_STALE = "possibly_stale"          # Signature changed, docs may be outdated
    NEEDS_UPDATE = "needs_update"              # Docstring changed, docs should sync
    ADDED_UNDOCUMENTED = "added_undocumented"  # New entity without documentation


@dataclass(frozen=True)
class DocumentationImpact:
    """
    Documentation that may be affected by a code change.

    Represents a single impact: one code change affecting one documentation reference.
    """
    doc_path: str
    doc_line: int
    referenced_entity: str
    impact_type: ImpactType
    confidence: float  # 0.0 to 1.0
    change: EntityChange

    def __post_init__(self) -> None:
        """Validate field constraints."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be 0.0-1.0, got {self.confidence}")

    def __str__(self) -> str:
        if self.doc_path:
            return f"{self.doc_path}:{self.doc_line} ({self.impact_type.value})"
        # ADDED_UNDOCUMENTED has no doc_path
        return f"{self.change.file_path}:{self.referenced_entity} ({self.impact_type.value})"

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "doc_path": self.doc_path,
            "doc_line": self.doc_line,
            "referenced_entity": self.referenced_entity,
            "impact_type": self.impact_type.value,
            "confidence": self.confidence,
            "severity": self.severity,
            "change": {
                "entity_name": self.change.entity_name,
                "entity_type": self.change.entity_type.value,
                "file_path": self.change.file_path,
                "change_type": self.change.change_type.value,
                "old_signature": self.change.old_signature,
                "new_signature": self.change.new_signature,
                "old_docstring": self.change.old_docstring,
                "new_docstring": self.change.new_docstring,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DocumentationImpact":
        """Reconstruct from dictionary."""
        change_data = data["change"]
        return cls(
            doc_path=data["doc_path"],
            doc_line=data["doc_line"],
            referenced_entity=data["referenced_entity"],
            impact_type=ImpactType(data["impact_type"]),
            confidence=data["confidence"],
            change=EntityChange(
                entity_name=change_data["entity_name"],
                entity_type=EntityType(change_data["entity_type"]),
                file_path=change_data["file_path"],
                change_type=ChangeType(change_data["change_type"]),
                old_signature=change_data.get("old_signature"),
                new_signature=change_data.get("new_signature"),
                old_docstring=change_data.get("old_docstring"),
                new_docstring=change_data.get("new_docstring"),
            ),
        )

    @property
    def severity(self) -> str:
        """Human-readable severity based on impact type."""
        severity_map = {
            ImpactType.BROKEN_REFERENCE: "high",
            ImpactType.POSSIBLY_STALE: "medium",
            ImpactType.NEEDS_UPDATE: "low",
            ImpactType.ADDED_UNDOCUMENTED: "low",
        }
        return severity_map.get(self.impact_type, "low")


class ImpactAnalyzer:
    """
    Analyze how code changes impact documentation.

    Uses the DocumentationGraph to find which docs reference changed entities,
    then assesses the impact based on the type of change.
    """

    def __init__(self, graph: DocumentationGraph):
        self.graph = graph

    def analyze_changes(self, changes: list[EntityChange]) -> list[DocumentationImpact]:
        """
        For each code change, find documentation that might be affected.

        Args:
            changes: List of entity changes from ChangeTracker.detect_entity_changes()

        Returns:
            List of DocumentationImpact objects describing affected docs
        """
        impacts: list[DocumentationImpact] = []

        for change in changes:
            # Find all docs that reference this entity
            doc_refs = self._find_doc_references(change)

            if doc_refs:
                # Assess impact on each existing reference
                for _, ref_data in doc_refs:
                    impact = self._assess_impact(change, ref_data)
                    if impact:
                        impacts.append(impact)
            elif change.change_type == ChangeType.ADDED:
                # New entity with no documentation coverage
                impacts.append(DocumentationImpact(
                    doc_path="",  # No doc file - that's the point
                    doc_line=0,
                    referenced_entity=change.entity_name,
                    impact_type=ImpactType.ADDED_UNDOCUMENTED,
                    confidence=CONFIDENCE_UNDOCUMENTED,
                    change=change,
                ))

        return impacts

    def _find_doc_references(
        self,
        change: EntityChange
    ) -> list[tuple[str, dict]]:
        """
        Find all documentation references for a changed entity.

        Maps the EntityChange to graph node IDs and queries for documenting refs.
        """
        # Build potential qualified names to search for
        qualified_names = self._build_qualified_names(change)

        # Use dict to deduplicate by ref_id
        refs_by_id: dict[str, dict] = {}

        for qualified_name in qualified_names:
            entity_id = self.graph.find_entity_by_qualified_name(qualified_name)
            if entity_id:
                ref_ids = self.graph.get_documenting_refs(entity_id)
                for ref_id in ref_ids:
                    if ref_id not in refs_by_id:
                        ref_data = self.graph.get_reference_data(ref_id)
                        if ref_data:
                            refs_by_id[ref_id] = ref_data

        return list(refs_by_id.items())

    def _build_qualified_names(self, change: EntityChange) -> list[str]:
        """
        Build possible qualified names for a changed entity.

        The entity_name from EntityChange might be just "func_name" or "Class.method",
        but the graph uses fully qualified names like "module.submodule.func_name".
        We try multiple possibilities.
        """
        module_path = file_path_to_module_path(Path(change.file_path))
        qualified_name = f"{module_path}.{change.entity_name}"

        # Try fully qualified first, then simple name as fallback
        return [qualified_name, change.entity_name]

    def _assess_impact(
        self,
        change: EntityChange,
        ref_data: dict
    ) -> Optional[DocumentationImpact]:
        """
        Assess how a specific change impacts a specific doc reference.

        Maps change types to impact types with appropriate confidence levels:
        - DELETED: Broken reference (confidence 1.0) - entity no longer exists
        - SIGNATURE_CHANGED: Possibly stale (confidence 0.8) - params/return may differ
        - DOCSTRING_CHANGED: Needs update (confidence 0.6) - docs may want to sync
        - BODY_CHANGED: No impact - implementation details don't affect docs
        - ADDED: No impact on existing refs - they can't reference new entities
        """
        # Parse location string using Location.from_str()
        location_str = ref_data.get("location", "")
        location = Location.from_str(location_str)
        if location:
            doc_path = str(location.file)
            doc_line = location.line_start
        else:
            doc_path = location_str
            doc_line = 0

        # Map change type to impact
        if change.change_type == ChangeType.DELETED:
            return DocumentationImpact(
                doc_path=doc_path,
                doc_line=doc_line,
                referenced_entity=change.entity_name,
                impact_type=ImpactType.BROKEN_REFERENCE,
                confidence=CONFIDENCE_BROKEN_REFERENCE,
                change=change,
            )

        if change.change_type == ChangeType.SIGNATURE_CHANGED:
            return DocumentationImpact(
                doc_path=doc_path,
                doc_line=doc_line,
                referenced_entity=change.entity_name,
                impact_type=ImpactType.POSSIBLY_STALE,
                confidence=CONFIDENCE_SIGNATURE_CHANGED,
                change=change,
            )

        if change.change_type == ChangeType.DOCSTRING_CHANGED:
            return DocumentationImpact(
                doc_path=doc_path,
                doc_line=doc_line,
                referenced_entity=change.entity_name,
                impact_type=ImpactType.NEEDS_UPDATE,
                confidence=CONFIDENCE_DOCSTRING_CHANGED,
                change=change,
            )

        # BODY_CHANGED and ADDED don't impact existing documentation
        return None

    def analyze_commit(
        self,
        commit: AnalyzedCommit,
        tracker: ChangeTracker
    ) -> list[DocumentationImpact]:
        """
        Convenience method to analyze all entity changes in a commit.

        Args:
            commit: The analyzed commit
            tracker: ChangeTracker instance to detect entity changes

        Returns:
            List of documentation impacts
        """
        entity_changes = tracker.detect_entity_changes(commit)
        return self.analyze_changes(entity_changes)

    def generate_report(self, impacts: list[DocumentationImpact]) -> str:
        """
        Generate a human-readable impact report.

        Args:
            impacts: List of documentation impacts to report

        Returns:
            Formatted string report
        """
        if not impacts:
            return "No documentation impacts detected."

        lines = ["# Documentation Impact Report", ""]

        # Group by severity
        by_severity: dict[str, list[DocumentationImpact]] = {
            "high": [],
            "medium": [],
            "low": [],
        }

        for impact in impacts:
            by_severity[impact.severity].append(impact)

        # Report high severity first
        for severity in ["high", "medium", "low"]:
            items = by_severity[severity]
            if not items:
                continue

            lines.append(f"## {severity.upper()} Priority ({len(items)} items)")
            lines.append("")

            for impact in items:
                if impact.impact_type == ImpactType.ADDED_UNDOCUMENTED:
                    # No doc location - show source file instead
                    lines.append(f"- **{impact.change.file_path}** (undocumented)")
                    lines.append(f"  - Entity: `{impact.referenced_entity}`")
                    lines.append(f"  - Issue: new {impact.change.entity_type.value} has no documentation")
                else:
                    lines.append(f"- **{impact.doc_path}:{impact.doc_line}**")
                    lines.append(f"  - References: `{impact.referenced_entity}`")
                    lines.append(f"  - Issue: {impact.impact_type.value.replace('_', ' ')}")
                    lines.append(f"  - Change: {impact.change.change_type.value} in `{impact.change.file_path}`")
                lines.append("")

        return "\n".join(lines)
