"""
Graph structure for code-documentation relationships.

Uses networkx as the single source of truth for all relationships.
The graph is purely structural - analysis logic is in analyzer.py.
"""
from pathlib import Path
from typing import Iterator, Optional

import networkx as nx

from docwatch.models import CodeEntity, DocReference, CodeFile, DocFile, CodeDocLink


# Node ID delimiter - pipe is invalid in file paths on Windows/Unix
_ID_DELIM = "|"


def _file_node_id(path: Path | str) -> str:
    """Generate a unique node ID for a file."""
    return f"file{_ID_DELIM}{path}"


def _entity_node_id(qualified_name: str) -> str:
    """Generate a unique node ID for a code entity."""
    return f"entity{_ID_DELIM}{qualified_name}"


def _reference_node_id(file: Path | str, line: int, text: str) -> str:
    """Generate a unique node ID for a documentation reference."""
    return f"ref{_ID_DELIM}{file}{_ID_DELIM}{line}{_ID_DELIM}{text}"


class DocumentationGraph:
    """
    Directed graph representing code-documentation relationships.

    Node types (identified by 'kind' attribute):
    - 'code_file': A source code file
    - 'doc_file': A documentation file
    - 'entity': A code entity (function, class, etc.)
    - 'reference': A documentation reference

    Edge types (identified by 'relation' attribute):
    - 'contains': File contains entity/reference
    - 'documents': Reference documents entity
    """

    def __init__(self):
        self._graph = nx.DiGraph()

    # --- Node management ---

    def add_code_file(self, code_file: CodeFile) -> str:
        """Add a code file and its entities. Returns node ID."""
        file_id = _file_node_id(code_file.path)
        self._graph.add_node(
            file_id,
            kind="code_file",
            path=str(code_file.path),
            language=code_file.language.value,
        )

        for entity in code_file.entities:
            entity_id = self.add_entity(entity)
            self._graph.add_edge(file_id, entity_id, relation="contains")

        return file_id

    def add_doc_file(self, doc_file: DocFile) -> str:
        """Add a doc file and its references. Returns node ID."""
        file_id = _file_node_id(doc_file.path)
        self._graph.add_node(
            file_id,
            kind="doc_file",
            path=str(doc_file.path),
            format=doc_file.format.value,
            title=doc_file.title,
        )

        for ref in doc_file.references:
            ref_id = self.add_reference(ref)
            self._graph.add_edge(file_id, ref_id, relation="contains")

        return file_id

    def add_entity(self, entity: CodeEntity) -> str:
        """Add a code entity. Returns node ID."""
        entity_id = _entity_node_id(entity.qualified_name)
        self._graph.add_node(
            entity_id,
            kind="entity",
            name=entity.name,
            qualified_name=entity.qualified_name,
            entity_type=entity.entity_type.value,
            location=str(entity.location),
        )
        return entity_id

    def add_reference(self, ref: DocReference) -> str:
        """Add a documentation reference. Returns node ID."""
        ref_id = _reference_node_id(
            ref.location.file,
            ref.location.line_start,
            ref.clean_text,
        )
        self._graph.add_node(
            ref_id,
            kind="reference",
            text=ref.text,
            clean_text=ref.clean_text,
            location=str(ref.location),
            ref_type=ref.reference_type.value,
        )
        return ref_id

    def add_link(self, link: CodeDocLink) -> None:
        """Add a documentation link (entity -> reference edge)."""
        entity_id = _entity_node_id(link.entity.qualified_name)
        ref_id = _reference_node_id(
            link.reference.location.file,
            link.reference.location.line_start,
            link.reference.clean_text,
        )

        if entity_id in self._graph and ref_id in self._graph:
            self._graph.add_edge(
                entity_id,
                ref_id,
                relation="documents",
                link_type=link.link_type.value,
                confidence=link.confidence,
            )

    # --- Queries ---

    def get_entities(self) -> Iterator[str]:
        """Iterate over all entity node IDs."""
        for node, data in self._graph.nodes(data=True):
            if data.get("kind") == "entity":
                yield node

    def get_references(self) -> Iterator[str]:
        """Iterate over all reference node IDs."""
        for node, data in self._graph.nodes(data=True):
            if data.get("kind") == "reference":
                yield node

    def get_entity_data(self, entity_id: str) -> Optional[dict]:
        """Get entity node data."""
        if entity_id in self._graph:
            return dict(self._graph.nodes[entity_id])
        return None

    def get_reference_data(self, ref_id: str) -> Optional[dict]:
        """Get reference node data."""
        if ref_id in self._graph:
            return dict(self._graph.nodes[ref_id])
        return None

    def find_entity_by_qualified_name(self, qualified_name: str) -> Optional[str]:
        """
        Find an entity node ID by its qualified name.

        Args:
            qualified_name: Full module.name identifier (e.g., "mypackage.module.func")

        Returns:
            Entity node ID if found, None otherwise
        """
        entity_id = _entity_node_id(qualified_name)
        if entity_id in self._graph:
            data = self._graph.nodes[entity_id]
            if data.get("kind") == "entity":
                return entity_id
        return None

    def get_documenting_refs(self, entity_id: str) -> list[str]:
        """Get all reference IDs that document an entity."""
        refs = []
        for _, target, data in self._graph.out_edges(entity_id, data=True):
            if data.get("relation") == "documents":
                refs.append(target)
        return refs

    def get_documented_entity(self, ref_id: str) -> Optional[str]:
        """Get the entity ID that a reference documents."""
        for source, _, data in self._graph.in_edges(ref_id, data=True):
            if data.get("relation") == "documents":
                return source
        return None

    def is_entity_documented(self, entity_id: str) -> bool:
        """Check if an entity has any documentation."""
        return len(self.get_documenting_refs(entity_id)) > 0

    def is_reference_linked(self, ref_id: str) -> bool:
        """Check if a reference is linked to any entity."""
        return self.get_documented_entity(ref_id) is not None

    # --- Cluster Analysis ---

    def get_connected_file_clusters(self) -> list[list[str]]:
        """
        Find groups of related code and documentation files.

        Uses graph connectivity to identify which files are connected
        through shared entities and references.

        Returns:
            List of clusters, where each cluster is a list of file paths.
            Sorted by cluster size (largest first).
        """
        # Convert to undirected for component analysis
        undirected = self._graph.to_undirected()

        # Find connected components
        clusters = []
        for component in nx.connected_components(undirected):
            # Extract just the file nodes (not entities/references)
            files = [
                node.split(_ID_DELIM, 1)[1]  # Remove "file|" prefix
                for node in component
                if node.startswith(f"file{_ID_DELIM}")
            ]
            if files:
                clusters.append(sorted(files))

        # Sort clusters by size (largest first)
        clusters.sort(key=len, reverse=True)
        return clusters

    # --- Stats ---

    @property
    def node_count(self) -> int:
        return self._graph.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self._graph.number_of_edges()

    def count_by_kind(self, kind: str) -> int:
        """Count nodes of a specific kind."""
        return sum(1 for _, d in self._graph.nodes(data=True) if d.get("kind") == kind)

    # --- Serialization ---

    def to_dict(self) -> dict:
        """Export graph as JSON-serializable dict."""
        return {
            "nodes": [
                {"id": n, **d}
                for n, d in self._graph.nodes(data=True)
            ],
            "edges": [
                {"source": u, "target": v, **d}
                for u, v, d in self._graph.edges(data=True)
            ],
        }
