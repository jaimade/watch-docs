"""
Tests for analyzer matching logic.

Covers exact, partial, and qualified matching with confidence scores.
"""
import pytest
import tempfile
import json
from pathlib import Path

from docwatch.models import (
    Language, DocFormat, EntityType, ReferenceType, LinkType,
    Location, CodeEntity, DocReference, CodeFile, DocFile
)
from docwatch.analyzer import DocumentationAnalyzer, CoverageStats


class TestCoverageStats:
    """Tests for CoverageStats dataclass."""

    def test_undocumented_entities_computed(self):
        """undocumented_entities is computed correctly."""
        stats = CoverageStats(
            total_entities=10,
            documented_entities=7,
            total_references=5,
            linked_references=3
        )
        assert stats.undocumented_entities == 3

    def test_broken_references_computed(self):
        """broken_references is computed correctly."""
        stats = CoverageStats(
            total_entities=10,
            documented_entities=7,
            total_references=5,
            linked_references=3
        )
        assert stats.broken_references == 2

    def test_coverage_percent_normal(self):
        """coverage_percent calculates correctly."""
        stats = CoverageStats(
            total_entities=100,
            documented_entities=75,
            total_references=50,
            linked_references=40
        )
        assert stats.coverage_percent == 75.0

    def test_coverage_percent_zero_entities(self):
        """coverage_percent returns 0 when no entities."""
        stats = CoverageStats(
            total_entities=0,
            documented_entities=0,
            total_references=5,
            linked_references=3
        )
        assert stats.coverage_percent == 0.0

    def test_to_dict(self):
        """to_dict includes all fields."""
        stats = CoverageStats(
            total_entities=10,
            documented_entities=8,
            total_references=5,
            linked_references=4
        )
        data = stats.to_dict()

        assert data["total_entities"] == 10
        assert data["documented_entities"] == 8
        assert data["undocumented_entities"] == 2
        assert data["coverage_percent"] == 80.0
        assert data["broken_references"] == 1


class TestAnalyzerMatching:
    """Tests for reference-to-entity matching."""

    def create_analyzer_with_entities(self, entities):
        """Helper to create analyzer with pre-loaded entities."""
        analyzer = DocumentationAnalyzer()
        code_file = CodeFile(
            path=Path("test.py"),
            language=Language.PYTHON,
            entities=entities
        )
        analyzer.code_files = [code_file]
        analyzer.graph.add_code_file(code_file)

        # Build entity index
        for entity in entities:
            if entity.name not in analyzer._entity_index:
                analyzer._entity_index[entity.name] = []
            analyzer._entity_index[entity.name].append(entity)

        # Reinitialize components so matcher has updated trigram index
        analyzer._init_components()

        return analyzer

    def test_exact_match(self):
        """Exact name match returns 1.0 confidence."""
        entities = [
            CodeEntity(
                name="process_data",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("test.py"), line_start=1)
            )
        ]
        analyzer = self.create_analyzer_with_entities(entities)

        ref = DocReference(
            text="process_data",
            location=Location(file=Path("README.md"), line_start=1),
            reference_type=ReferenceType.INLINE_CODE
        )

        matches = analyzer._match_reference(ref)

        assert len(matches) == 1
        entity, link_type, confidence = matches[0]
        assert entity.name == "process_data"
        assert link_type == LinkType.EXACT
        assert confidence == 1.0

    def test_exact_match_multiple_entities(self):
        """Exact match finds all entities with same name."""
        entities = [
            CodeEntity(
                name="helper",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("utils.py"), line_start=1)
            ),
            CodeEntity(
                name="helper",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("tools.py"), line_start=1)
            ),
        ]
        analyzer = self.create_analyzer_with_entities(entities)

        ref = DocReference(
            text="helper",
            location=Location(file=Path("README.md"), line_start=1),
            reference_type=ReferenceType.INLINE_CODE
        )

        matches = analyzer._match_reference(ref)

        assert len(matches) == 2
        assert all(m[1] == LinkType.EXACT for m in matches)
        assert all(m[2] == 1.0 for m in matches)

    def test_qualified_match(self):
        """Qualified reference 'module.func' matches 'func'."""
        entities = [
            CodeEntity(
                name="process",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("src/utils.py"), line_start=1)
            )
        ]
        analyzer = self.create_analyzer_with_entities(entities)

        ref = DocReference(
            text="utils.process",
            location=Location(file=Path("README.md"), line_start=1),
            reference_type=ReferenceType.INLINE_CODE
        )

        matches = analyzer._match_reference(ref)

        assert len(matches) >= 1
        # Should have qualified or partial match
        link_types = [m[1] for m in matches]
        assert LinkType.QUALIFIED in link_types or LinkType.PARTIAL in link_types

    def test_partial_match_substring(self):
        """Partial match finds entities containing reference text."""
        entities = [
            CodeEntity(
                name="process_data_batch",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("test.py"), line_start=1)
            )
        ]
        analyzer = self.create_analyzer_with_entities(entities)

        ref = DocReference(
            text="process_data",
            location=Location(file=Path("README.md"), line_start=1),
            reference_type=ReferenceType.INLINE_CODE
        )

        matches = analyzer._match_reference(ref)

        # Should find partial match since "process_data" is in "process_data_batch"
        assert len(matches) >= 1
        assert any(m[1] == LinkType.PARTIAL for m in matches)

    def test_no_match(self):
        """Non-existent reference returns empty list."""
        entities = [
            CodeEntity(
                name="existing_function",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("test.py"), line_start=1)
            )
        ]
        analyzer = self.create_analyzer_with_entities(entities)

        ref = DocReference(
            text="nonexistent",
            location=Location(file=Path("README.md"), line_start=1),
            reference_type=ReferenceType.INLINE_CODE
        )

        matches = analyzer._match_reference(ref)

        assert matches == []

    def test_code_block_confidence_penalty(self):
        """Code block references get 0.6x confidence penalty."""
        entities = [
            CodeEntity(
                name="process_data",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("test.py"), line_start=1)
            )
        ]
        analyzer = self.create_analyzer_with_entities(entities)

        # Inline code reference
        inline_ref = DocReference(
            text="process_data",
            location=Location(file=Path("README.md"), line_start=1),
            reference_type=ReferenceType.INLINE_CODE
        )

        # Code block reference
        block_ref = DocReference(
            text="process_data",
            location=Location(file=Path("README.md"), line_start=10),
            reference_type=ReferenceType.CODE_BLOCK
        )

        inline_matches = analyzer._match_reference(inline_ref)
        block_matches = analyzer._match_reference(block_ref)

        assert len(inline_matches) == 1
        assert len(block_matches) == 1

        inline_confidence = inline_matches[0][2]
        block_confidence = block_matches[0][2]

        assert inline_confidence == 1.0
        assert block_confidence == 0.6  # 1.0 * 0.6 penalty

    def test_short_reference_ignored(self):
        """References shorter than 3 chars don't get partial matches."""
        entities = [
            CodeEntity(
                name="xyz",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("test.py"), line_start=1)
            )
        ]
        analyzer = self.create_analyzer_with_entities(entities)

        ref = DocReference(
            text="xy",  # Only 2 chars
            location=Location(file=Path("README.md"), line_start=1),
            reference_type=ReferenceType.INLINE_CODE
        )

        matches = analyzer._match_reference(ref)

        # Short reference should not get partial match
        # (exact match would work if "xy" existed)
        partial_matches = [m for m in matches if m[1] == LinkType.PARTIAL]
        assert len(partial_matches) == 0


class TestAnalyzerCoverage:
    """Tests for coverage calculation."""

    def test_get_coverage_stats_empty(self):
        """Empty analyzer returns zero coverage."""
        analyzer = DocumentationAnalyzer()
        stats = analyzer.get_coverage_stats()

        assert stats.total_entities == 0
        assert stats.documented_entities == 0
        assert stats.coverage_percent == 0.0

    def test_get_coverage_stats_with_data(self):
        """Coverage stats calculated correctly with data."""
        analyzer = DocumentationAnalyzer()

        # Add code file with entities
        code_file = CodeFile(
            path=Path("app.py"),
            language=Language.PYTHON,
            entities=[
                CodeEntity(
                    name="func_a",
                    entity_type=EntityType.FUNCTION,
                    location=Location(file=Path("app.py"), line_start=1)
                ),
                CodeEntity(
                    name="func_b",
                    entity_type=EntityType.FUNCTION,
                    location=Location(file=Path("app.py"), line_start=10)
                ),
            ]
        )
        analyzer.code_files = [code_file]
        analyzer.graph.add_code_file(code_file)

        # Build entity index
        for entity in code_file.entities:
            analyzer._entity_index[entity.name] = [entity]

        # Add doc file with references
        doc_file = DocFile(
            path=Path("README.md"),
            format=DocFormat.MARKDOWN,
            references=[
                DocReference(
                    text="func_a",
                    location=Location(file=Path("README.md"), line_start=1),
                    reference_type=ReferenceType.INLINE_CODE
                ),
                DocReference(
                    text="nonexistent",
                    location=Location(file=Path("README.md"), line_start=5),
                    reference_type=ReferenceType.INLINE_CODE
                ),
            ]
        )
        analyzer.doc_files = [doc_file]
        analyzer.graph.add_doc_file(doc_file)

        # Build links
        analyzer._build_links()

        stats = analyzer.get_coverage_stats()

        assert stats.total_entities == 2
        assert stats.documented_entities == 1  # func_a is documented
        assert stats.total_references == 2
        assert stats.linked_references == 1  # func_a linked
        assert stats.broken_references == 1  # nonexistent is broken

    def test_get_undocumented_entities(self):
        """get_undocumented_entities returns correct list."""
        analyzer = DocumentationAnalyzer()

        entities = [
            CodeEntity(
                name="documented_func",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("app.py"), line_start=1)
            ),
            CodeEntity(
                name="undocumented_func",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("app.py"), line_start=10)
            ),
        ]
        code_file = CodeFile(
            path=Path("app.py"),
            language=Language.PYTHON,
            entities=entities
        )
        analyzer.code_files = [code_file]
        analyzer.graph.add_code_file(code_file)

        for entity in entities:
            analyzer._entity_index[entity.name] = [entity]

        # Only document one function
        doc_file = DocFile(
            path=Path("README.md"),
            format=DocFormat.MARKDOWN,
            references=[
                DocReference(
                    text="documented_func",
                    location=Location(file=Path("README.md"), line_start=1),
                    reference_type=ReferenceType.INLINE_CODE
                ),
            ]
        )
        analyzer.doc_files = [doc_file]
        analyzer.graph.add_doc_file(doc_file)
        analyzer._build_links()

        undocumented = analyzer.get_undocumented_entities()

        assert len(undocumented) == 1
        assert undocumented[0].name == "undocumented_func"

    def test_get_broken_references(self):
        """get_broken_references returns correct list."""
        analyzer = DocumentationAnalyzer()

        # Add entity
        entity = CodeEntity(
            name="real_func",
            entity_type=EntityType.FUNCTION,
            location=Location(file=Path("app.py"), line_start=1)
        )
        code_file = CodeFile(
            path=Path("app.py"),
            language=Language.PYTHON,
            entities=[entity]
        )
        analyzer.code_files = [code_file]
        analyzer.graph.add_code_file(code_file)
        analyzer._entity_index[entity.name] = [entity]

        # Add references - one valid, one broken
        doc_file = DocFile(
            path=Path("README.md"),
            format=DocFormat.MARKDOWN,
            references=[
                DocReference(
                    text="real_func",
                    location=Location(file=Path("README.md"), line_start=1),
                    reference_type=ReferenceType.INLINE_CODE
                ),
                DocReference(
                    text="fake_func",
                    location=Location(file=Path("README.md"), line_start=5),
                    reference_type=ReferenceType.INLINE_CODE
                ),
            ]
        )
        analyzer.doc_files = [doc_file]
        analyzer.graph.add_doc_file(doc_file)
        analyzer._build_links()

        broken = analyzer.get_broken_references()

        assert len(broken) == 1
        assert broken[0].clean_text == "fake_func"


class TestAnalyzerPersistence:
    """Tests for save/load functionality."""

    def test_save_and_load_round_trip(self):
        """Analyzer state survives save/load cycle."""
        # Create analyzer with data
        original = DocumentationAnalyzer()

        entity = CodeEntity(
            name="my_func",
            entity_type=EntityType.FUNCTION,
            location=Location(file=Path("app.py"), line_start=42)
        )
        code_file = CodeFile(
            path=Path("app.py"),
            language=Language.PYTHON,
            entities=[entity]
        )
        original.code_files = [code_file]
        original.graph.add_code_file(code_file)
        original._entity_index[entity.name] = [entity]

        ref = DocReference(
            text="my_func",
            location=Location(file=Path("README.md"), line_start=10),
            reference_type=ReferenceType.INLINE_CODE
        )
        doc_file = DocFile(
            path=Path("README.md"),
            format=DocFormat.MARKDOWN,
            references=[ref]
        )
        original.doc_files = [doc_file]
        original.graph.add_doc_file(doc_file)
        original._build_links()

        original_stats = original.get_coverage_stats()

        # Save and load
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            save_path = Path(f.name)

        try:
            original.save(save_path)
            loaded = DocumentationAnalyzer.load(save_path)

            loaded_stats = loaded.get_coverage_stats()

            assert loaded_stats.total_entities == original_stats.total_entities
            assert loaded_stats.documented_entities == original_stats.documented_entities
            assert len(loaded.links) == len(original.links)
            assert len(loaded.code_files) == len(original.code_files)
            assert len(loaded.doc_files) == len(original.doc_files)
        finally:
            save_path.unlink()

    def test_save_creates_valid_json(self):
        """save() creates valid JSON file."""
        analyzer = DocumentationAnalyzer()

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            save_path = Path(f.name)

        try:
            analyzer.save(save_path)

            with open(save_path) as f:
                data = json.load(f)

            assert "version" in data
            assert "created_at" in data
            assert "code_files" in data
            assert "doc_files" in data
            assert "links" in data
        finally:
            save_path.unlink()


class TestAnalyzerPriorityScoring:
    """Tests for priority issue scoring."""

    def test_public_class_high_priority(self):
        """Public class without docs gets high priority."""
        analyzer = DocumentationAnalyzer()

        entity = CodeEntity(
            name="PublicClass",
            entity_type=EntityType.CLASS,
            location=Location(file=Path("app.py"), line_start=1)
        )

        score, reason = analyzer._score_undocumented_entity(entity)

        assert score >= 0.7  # High priority
        assert "class" in reason.lower()
        assert "public" in reason.lower()

    def test_private_function_low_priority(self):
        """Private function without docs gets low priority."""
        analyzer = DocumentationAnalyzer()

        entity = CodeEntity(
            name="_private_helper",
            entity_type=EntityType.FUNCTION,
            location=Location(file=Path("app.py"), line_start=1)
        )

        score, reason = analyzer._score_undocumented_entity(entity)

        assert score <= 0.4  # Low priority
        assert "private" in reason.lower()

    def test_dunder_method_very_low_priority(self):
        """Dunder methods get very low priority."""
        analyzer = DocumentationAnalyzer()

        entity = CodeEntity(
            name="__init__",
            entity_type=EntityType.METHOD,
            location=Location(file=Path("app.py"), line_start=1),
            parent="MyClass"
        )

        score, reason = analyzer._score_undocumented_entity(entity)

        assert score <= 0.3  # Very low priority
        assert "dunder" in reason.lower()

    def test_prominent_broken_ref_higher_priority(self):
        """Broken reference early in file gets higher priority."""
        analyzer = DocumentationAnalyzer()

        early_ref = DocReference(
            text="missing_func",
            location=Location(file=Path("README.md"), line_start=5),
            reference_type=ReferenceType.INLINE_CODE
        )
        late_ref = DocReference(
            text="another_missing",
            location=Location(file=Path("README.md"), line_start=100),
            reference_type=ReferenceType.INLINE_CODE
        )

        early_score, _ = analyzer._score_broken_reference(early_ref)
        late_score, _ = analyzer._score_broken_reference(late_ref)

        assert early_score > late_score


class TestCoverageByFile:
    """Tests for per-file coverage calculation."""

    def test_coverage_by_file_empty(self):
        """Empty analyzer returns empty dict."""
        analyzer = DocumentationAnalyzer()
        coverage = analyzer.get_coverage_by_file()
        assert coverage == {}

    def test_coverage_by_file_no_entities(self):
        """File with no entities shows 100% coverage."""
        analyzer = DocumentationAnalyzer()

        code_file = CodeFile(
            path=Path("empty.py"),
            language=Language.PYTHON,
            entities=[]  # No entities
        )
        analyzer.code_files = [code_file]

        coverage = analyzer.get_coverage_by_file()

        assert coverage[str(code_file.path)] == 100.0

    def test_coverage_by_file_partial(self):
        """Partial coverage calculated correctly per file."""
        analyzer = DocumentationAnalyzer()

        # File with 2 entities, 1 documented
        entities = [
            CodeEntity(
                name="documented",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("app.py"), line_start=1)
            ),
            CodeEntity(
                name="undocumented",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("app.py"), line_start=10)
            ),
        ]
        code_file = CodeFile(
            path=Path("app.py"),
            language=Language.PYTHON,
            entities=entities
        )
        analyzer.code_files = [code_file]
        analyzer.graph.add_code_file(code_file)

        for entity in entities:
            analyzer._entity_index[entity.name] = [entity]

        # Document only one
        doc_file = DocFile(
            path=Path("README.md"),
            format=DocFormat.MARKDOWN,
            references=[
                DocReference(
                    text="documented",
                    location=Location(file=Path("README.md"), line_start=1),
                    reference_type=ReferenceType.INLINE_CODE
                ),
            ]
        )
        analyzer.doc_files = [doc_file]
        analyzer.graph.add_doc_file(doc_file)
        analyzer._build_links()

        coverage = analyzer.get_coverage_by_file()

        assert coverage[str(code_file.path)] == 50.0
