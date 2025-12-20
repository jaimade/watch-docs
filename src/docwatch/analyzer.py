"""
Analysis logic for documentation coverage.

This module handles:
- Building the documentation graph from parsed files
- Matching references to code entities
- Computing coverage statistics
- Finding documentation issues
"""
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from docwatch.models import (
    CodeFile, DocFile, CodeEntity, DocReference,
    CodeDocLink, LinkType, ReferenceType
)
from docwatch.graph import DocumentationGraph
from docwatch.extractor import process_directory


@dataclass
class CoverageStats:
    """Documentation coverage statistics."""
    total_entities: int
    documented_entities: int
    total_references: int
    linked_references: int

    @property
    def undocumented_entities(self) -> int:
        return self.total_entities - self.documented_entities

    @property
    def broken_references(self) -> int:
        return self.total_references - self.linked_references

    @property
    def coverage_percent(self) -> float:
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


class DocumentationAnalyzer:
    """
    Analyzes documentation coverage for a codebase.

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

        # Build graph
        for code_file in self.code_files:
            self.graph.add_code_file(code_file)
            # Index entities for matching
            for entity in code_file.entities:
                if entity.name not in self._entity_index:
                    self._entity_index[entity.name] = []
                self._entity_index[entity.name].append(entity)

        for doc_file in self.doc_files:
            self.graph.add_doc_file(doc_file)

        # Match references to entities
        self._build_links()

    def _build_links(self) -> None:
        """Match documentation references to code entities."""
        self.links.clear()

        for doc_file in self.doc_files:
            for ref in doc_file.references:
                matches = self._match_reference(ref)
                for entity, link_type, confidence in matches:
                    link = CodeDocLink(
                        entity=entity,
                        reference=ref,
                        link_type=link_type,
                        confidence=confidence,
                    )
                    self.links.append(link)
                    self.graph.add_link(link)

    def _match_reference(
        self, ref: DocReference
    ) -> list[tuple[CodeEntity, LinkType, float]]:
        """
        Find code entities matching a reference.

        Returns list of (entity, link_type, confidence) tuples.
        Code block references get a confidence penalty (0.6x) since
        they represent weaker documentation than inline prose.
        """
        clean_text = ref.clean_text
        matches = []

        # Code block references are weaker documentation
        confidence_multiplier = 0.6 if ref.reference_type == ReferenceType.CODE_BLOCK else 1.0

        # Exact name match
        if clean_text in self._entity_index:
            for entity in self._entity_index[clean_text]:
                confidence = 1.0 * confidence_multiplier
                matches.append((entity, LinkType.EXACT, confidence))
            return matches  # Exact match found, no need for fuzzy

        # Qualified match (e.g., "module.func" matches "func")
        if "." in clean_text:
            last_part = clean_text.split(".")[-1]
            if last_part in self._entity_index:
                for entity in self._entity_index[last_part]:
                    # Higher confidence if qualified name contains reference
                    if clean_text in entity.qualified_name:
                        confidence = 0.9 * confidence_multiplier
                        matches.append((entity, LinkType.QUALIFIED, confidence))
                    else:
                        confidence = 0.7 * confidence_multiplier
                        matches.append((entity, LinkType.PARTIAL, confidence))

        # Partial match (substring)
        if not matches:
            for name, entities in self._entity_index.items():
                if len(clean_text) >= 3 and (clean_text in name or name in clean_text):
                    for entity in entities:
                        confidence = 0.5 * confidence_multiplier
                        matches.append((entity, LinkType.PARTIAL, confidence))

        return matches

    def get_coverage_stats(self) -> CoverageStats:
        """Get documentation coverage statistics."""
        total_entities = sum(len(cf.entities) for cf in self.code_files)
        total_refs = sum(len(df.references) for df in self.doc_files)

        # Count unique documented entities
        documented = set()
        for link in self.links:
            documented.add(link.entity.qualified_name)

        # Count unique linked references
        linked_refs = set()
        for link in self.links:
            key = (str(link.reference.location.file), link.reference.location.line_start)
            linked_refs.add(key)

        return CoverageStats(
            total_entities=total_entities,
            documented_entities=len(documented),
            total_references=total_refs,
            linked_references=len(linked_refs),
        )

    def get_undocumented_entities(self) -> list[CodeEntity]:
        """Get all entities without documentation."""
        documented = {link.entity.qualified_name for link in self.links}

        undocumented = []
        for code_file in self.code_files:
            for entity in code_file.entities:
                if entity.qualified_name not in documented:
                    undocumented.append(entity)

        return undocumented

    def get_broken_references(self) -> list[DocReference]:
        """Get all references that don't match any code."""
        linked = {
            (str(link.reference.location.file), link.reference.location.line_start)
            for link in self.links
        }

        broken = []
        for doc_file in self.doc_files:
            for ref in doc_file.references:
                key = (str(ref.location.file), ref.location.line_start)
                if key not in linked:
                    broken.append(ref)

        return broken

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

    def get_coverage_by_file(self) -> dict[str, float]:
        """
        Get documentation coverage percentage for each code file.

        Returns:
            Dict mapping file path to coverage percentage (0.0 to 100.0)
        """
        # Build set of documented entity qualified names
        documented = {link.entity.qualified_name for link in self.links}

        coverage = {}
        for code_file in self.code_files:
            if not code_file.entities:
                coverage[str(code_file.path)] = 100.0  # No entities = fully covered
                continue

            documented_count = sum(
                1 for entity in code_file.entities
                if entity.qualified_name in documented
            )
            percentage = (documented_count / len(code_file.entities)) * 100
            coverage[str(code_file.path)] = round(percentage, 2)

        return coverage

    def find_documentation_clusters(self) -> list[list[str]]:
        """
        Find groups of related code and documentation files.

        Uses graph connectivity to identify which code files are
        documented together. Useful for understanding documentation structure.

        Returns:
            List of clusters, where each cluster is a list of file paths
            (both code and doc files that are related)
        """
        import networkx as nx

        # Get the underlying graph
        graph = self.graph._graph

        # Convert to undirected for component analysis
        undirected = graph.to_undirected()

        # Find connected components
        clusters = []
        for component in nx.connected_components(undirected):
            # Extract just the file nodes (not entities/references)
            files = [
                node.replace("file:", "")
                for node in component
                if node.startswith("file:")
            ]
            if files:
                clusters.append(sorted(files))

        # Sort clusters by size (largest first)
        clusters.sort(key=len, reverse=True)
        return clusters

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
            priority, reason = self._calculate_priority(entity, issue_type="undocumented")
            issues.append({
                "type": "undocumented",
                "priority": priority,
                "entity": entity.to_dict(),
                "reference": None,
                "reason": reason,
            })

        # Collect broken references
        for ref in self.get_broken_references():
            priority, reason = self._calculate_priority(ref, issue_type="broken_reference")
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

    def _calculate_priority(self, item, issue_type: str) -> tuple[float, str]:
        """
        Calculate priority score for an issue.

        Args:
            item: Either a CodeEntity (for undocumented) or DocReference (for broken)
            issue_type: "undocumented" or "broken_reference"

        Returns:
            Tuple of (priority_score, reason_string)
            - priority_score: float from 0.0 (low) to 1.0 (critical)
            - reason_string: explanation of why this priority was assigned
        """
        from docwatch.models import EntityType, ReferenceType

        if issue_type == "undocumented":
            return self._score_undocumented_entity(item)
        else:
            return self._score_broken_reference(item)

    def _score_undocumented_entity(self, entity: CodeEntity) -> tuple[float, str]:
        """Score an undocumented code entity."""
        from docwatch.models import EntityType

        score = 0.5  # Base score
        reasons = []

        # Classes are more important than functions
        if entity.entity_type == EntityType.CLASS:
            score += 0.2
            reasons.append("class")
        elif entity.entity_type == EntityType.FUNCTION:
            score += 0.1
            reasons.append("function")

        # Public vs private (underscore prefix)
        if entity.name.startswith("_"):
            score -= 0.3
            reasons.append("private")
        else:
            score += 0.2
            reasons.append("public API")

        # Methods inside classes are slightly less urgent than standalone
        if entity.parent:
            score -= 0.1
            reasons.append(f"method of {entity.parent}")

        # Dunder methods are low priority (usually self-documenting)
        if entity.name.startswith("__") and entity.name.endswith("__"):
            score -= 0.3
            reasons.append("dunder method")

        # Clamp score to valid range
        score = max(0.0, min(1.0, score))

        reason = f"Undocumented {', '.join(reasons)}"
        return (round(score, 2), reason)

    def _score_broken_reference(self, ref: DocReference) -> tuple[float, str]:
        """Score a broken documentation reference."""
        from docwatch.models import ReferenceType

        score = 0.5  # Base score
        reasons = []

        # References early in file are more visible
        if ref.location.line_start <= 20:
            score += 0.2
            reasons.append("prominent location")
        elif ref.location.line_start <= 50:
            score += 0.1
            reasons.append("visible location")

        # Headers are more important than inline code
        if ref.reference_type == ReferenceType.HEADER:
            score += 0.2
            reasons.append("in header")
        elif ref.reference_type == ReferenceType.CODE_BLOCK:
            score += 0.1
            reasons.append("in code block")

        # Check if reference looks like it might be a typo of existing entity
        close_matches = self._find_close_matches(ref.clean_text)
        if close_matches:
            score += 0.2
            reasons.append(f"similar to '{close_matches[0]}'")

        # Clamp score to valid range
        score = max(0.0, min(1.0, score))

        reason = f"Broken reference: {', '.join(reasons)}" if reasons else "Broken reference"
        return (round(score, 2), reason)

    def _find_close_matches(self, text: str, cutoff: float = 0.6) -> list[str]:
        """Find entity names similar to the given text."""
        import difflib

        all_names = list(self._entity_index.keys())
        return difflib.get_close_matches(text, all_names, n=1, cutoff=cutoff)

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
        data = {
            "version": "1.0",
            "created_at": datetime.now().isoformat(),
            "code_files": [cf.to_dict() for cf in self.code_files],
            "doc_files": [df.to_dict() for df in self.doc_files],
            "links": [link.to_dict() for link in self.links],
        }

        filepath = Path(filepath)
        with filepath.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: Path) -> "DocumentationAnalyzer":
        """
        Load an analysis from a JSON file.

        Args:
            filepath: Path to the JSON file

        Returns:
            DocumentationAnalyzer with restored state
        """
        filepath = Path(filepath)
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)

        analyzer = cls()

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

        return analyzer
