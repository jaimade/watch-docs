"""
Tests for model serialization round-trips.

Verifies that all models can be serialized to dict and reconstructed
without data loss.
"""
import pytest
from pathlib import Path

from docwatch.models import (
    Language, DocFormat, EntityType, ReferenceType, LinkType,
    Location, CodeEntity, DocReference, CodeDocLink, CodeFile, DocFile
)


class TestLocation:
    """Tests for Location model."""

    def test_round_trip_basic(self):
        """Basic location serializes and deserializes correctly."""
        original = Location(
            file=Path("src/main.py"),
            line_start=42
        )

        data = original.to_dict()
        restored = Location.from_dict(data)

        assert restored.file == original.file
        assert restored.line_start == original.line_start
        assert restored.line_end is None

    def test_round_trip_with_line_end(self):
        """Location with line_end preserves both values."""
        original = Location(
            file=Path("src/utils.py"),
            line_start=10,
            line_end=25
        )

        data = original.to_dict()
        restored = Location.from_dict(data)

        assert restored.line_start == 10
        assert restored.line_end == 25
        assert restored.span == 16

    def test_to_dict_converts_path_to_string(self):
        """to_dict converts Path to string for JSON compatibility."""
        loc = Location(file=Path("src/test.py"), line_start=1)
        data = loc.to_dict()

        assert isinstance(data["file"], str)
        assert data["file"] == "src/test.py"

    def test_from_dict_converts_string_to_path(self):
        """from_dict converts string back to Path."""
        data = {"file": "src/test.py", "line_start": 1, "line_end": None}
        loc = Location.from_dict(data)

        assert isinstance(loc.file, Path)


class TestCodeEntity:
    """Tests for CodeEntity model."""

    def test_round_trip_function(self):
        """Function entity round-trips correctly."""
        original = CodeEntity(
            name="process_data",
            entity_type=EntityType.FUNCTION,
            location=Location(file=Path("src/app.py"), line_start=42)
        )

        data = original.to_dict()
        restored = CodeEntity.from_dict(data)

        assert restored.name == "process_data"
        assert restored.entity_type == EntityType.FUNCTION
        assert restored.location.line_start == 42

    def test_round_trip_class_with_all_fields(self):
        """Class with all optional fields round-trips correctly."""
        original = CodeEntity(
            name="MyClass",
            entity_type=EntityType.CLASS,
            location=Location(file=Path("src/models.py"), line_start=10, line_end=50),
            signature="class MyClass(Base):",
            docstring="A sample class for testing.",
            parent=None
        )

        data = original.to_dict()
        restored = CodeEntity.from_dict(data)

        assert restored.name == "MyClass"
        assert restored.signature == "class MyClass(Base):"
        assert restored.docstring == "A sample class for testing."

    def test_round_trip_method_with_parent(self):
        """Method with parent class round-trips correctly."""
        original = CodeEntity(
            name="get_value",
            entity_type=EntityType.METHOD,
            location=Location(file=Path("src/models.py"), line_start=25),
            parent="MyClass"
        )

        data = original.to_dict()
        restored = CodeEntity.from_dict(data)

        assert restored.parent == "MyClass"
        assert restored.display_name == "MyClass.get_value"

    def test_qualified_name_preserved(self):
        """qualified_name is included in to_dict but computed on restore."""
        entity = CodeEntity(
            name="helper",
            entity_type=EntityType.FUNCTION,
            location=Location(file=Path("src/utils.py"), line_start=1)
        )

        data = entity.to_dict()
        assert "qualified_name" in data

        # Restored entity computes its own qualified_name
        restored = CodeEntity.from_dict(data)
        assert restored.qualified_name == entity.qualified_name


class TestDocReference:
    """Tests for DocReference model."""

    def test_round_trip_inline_code(self):
        """Inline code reference round-trips correctly."""
        original = DocReference(
            text="`process_data`",
            location=Location(file=Path("README.md"), line_start=15),
            reference_type=ReferenceType.INLINE_CODE
        )

        data = original.to_dict()
        restored = DocReference.from_dict(data)

        assert restored.text == "`process_data`"
        assert restored.clean_text == "process_data"
        assert restored.reference_type == ReferenceType.INLINE_CODE

    def test_round_trip_code_block(self):
        """Code block reference round-trips correctly."""
        original = DocReference(
            text="DocumentationAnalyzer",
            location=Location(file=Path("docs/api.md"), line_start=42),
            reference_type=ReferenceType.CODE_BLOCK,
            context="from docwatch import DocumentationAnalyzer"
        )

        data = original.to_dict()
        restored = DocReference.from_dict(data)

        assert restored.reference_type == ReferenceType.CODE_BLOCK
        assert restored.context == "from docwatch import DocumentationAnalyzer"

    def test_clean_text_strips_formatting(self):
        """clean_text property removes backticks and quotes."""
        ref = DocReference(
            text="'my_function'",
            location=Location(file=Path("test.md"), line_start=1),
            reference_type=ReferenceType.INLINE_CODE
        )

        assert ref.clean_text == "my_function"


class TestCodeDocLink:
    """Tests for CodeDocLink model."""

    def test_round_trip(self):
        """CodeDocLink round-trips with nested models."""
        entity = CodeEntity(
            name="process",
            entity_type=EntityType.FUNCTION,
            location=Location(file=Path("src/app.py"), line_start=10)
        )
        reference = DocReference(
            text="process",
            location=Location(file=Path("README.md"), line_start=5),
            reference_type=ReferenceType.INLINE_CODE
        )
        original = CodeDocLink(
            entity=entity,
            reference=reference,
            link_type=LinkType.EXACT,
            confidence=1.0
        )

        data = original.to_dict()
        restored = CodeDocLink.from_dict(data)

        assert restored.entity.name == "process"
        assert restored.reference.text == "process"
        assert restored.link_type == LinkType.EXACT
        assert restored.confidence == 1.0

    def test_all_link_types(self):
        """All LinkType values serialize correctly."""
        for link_type in LinkType:
            entity = CodeEntity(
                name="test",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("test.py"), line_start=1)
            )
            ref = DocReference(
                text="test",
                location=Location(file=Path("test.md"), line_start=1),
                reference_type=ReferenceType.INLINE_CODE
            )
            link = CodeDocLink(
                entity=entity,
                reference=ref,
                link_type=link_type,
                confidence=0.5
            )

            data = link.to_dict()
            restored = CodeDocLink.from_dict(data)

            assert restored.link_type == link_type


class TestCodeFile:
    """Tests for CodeFile model."""

    def test_round_trip_empty(self):
        """Empty CodeFile round-trips correctly."""
        original = CodeFile(
            path=Path("src/empty.py"),
            language=Language.PYTHON
        )

        data = original.to_dict()
        restored = CodeFile.from_dict(data)

        assert restored.path == Path("src/empty.py")
        assert restored.language == Language.PYTHON
        assert restored.entities == []
        assert restored.imports == []

    def test_round_trip_with_entities(self):
        """CodeFile with entities round-trips correctly."""
        entities = [
            CodeEntity(
                name="main",
                entity_type=EntityType.FUNCTION,
                location=Location(file=Path("src/app.py"), line_start=1)
            ),
            CodeEntity(
                name="App",
                entity_type=EntityType.CLASS,
                location=Location(file=Path("src/app.py"), line_start=10)
            ),
        ]
        original = CodeFile(
            path=Path("src/app.py"),
            language=Language.PYTHON,
            entities=entities,
            imports=["os", "sys", "pathlib"]
        )

        data = original.to_dict()
        restored = CodeFile.from_dict(data)

        assert len(restored.entities) == 2
        assert restored.entities[0].name == "main"
        assert restored.entities[1].name == "App"
        assert restored.imports == ["os", "sys", "pathlib"]

    def test_all_languages(self):
        """All Language values serialize correctly."""
        for lang in Language:
            cf = CodeFile(path=Path("test.txt"), language=lang)
            data = cf.to_dict()
            restored = CodeFile.from_dict(data)
            assert restored.language == lang


class TestDocFile:
    """Tests for DocFile model."""

    def test_round_trip_empty(self):
        """Empty DocFile round-trips correctly."""
        original = DocFile(
            path=Path("docs/empty.md"),
            format=DocFormat.MARKDOWN
        )

        data = original.to_dict()
        restored = DocFile.from_dict(data)

        assert restored.path == Path("docs/empty.md")
        assert restored.format == DocFormat.MARKDOWN
        assert restored.title is None
        assert restored.references == []

    def test_round_trip_with_references(self):
        """DocFile with references round-trips correctly."""
        refs = [
            DocReference(
                text="function_one",
                location=Location(file=Path("README.md"), line_start=10),
                reference_type=ReferenceType.INLINE_CODE
            ),
            DocReference(
                text="ClassTwo",
                location=Location(file=Path("README.md"), line_start=20),
                reference_type=ReferenceType.CODE_BLOCK
            ),
        ]
        headers = [
            {"level": 1, "text": "Introduction", "line": 1},
            {"level": 2, "text": "Usage", "line": 5},
        ]
        original = DocFile(
            path=Path("README.md"),
            format=DocFormat.MARKDOWN,
            title="Introduction",
            references=refs,
            headers=headers
        )

        data = original.to_dict()
        restored = DocFile.from_dict(data)

        assert restored.title == "Introduction"
        assert len(restored.references) == 2
        assert restored.references[0].text == "function_one"
        assert restored.headers == headers

    def test_all_formats(self):
        """All DocFormat values serialize correctly."""
        for fmt in DocFormat:
            df = DocFile(path=Path("test.txt"), format=fmt)
            data = df.to_dict()
            restored = DocFile.from_dict(data)
            assert restored.format == fmt


class TestEnumMappings:
    """Tests for enum from_extension methods."""

    @pytest.mark.parametrize("ext,expected", [
        (".py", Language.PYTHON),
        (".pyi", Language.PYTHON),
        (".js", Language.JAVASCRIPT),
        (".ts", Language.TYPESCRIPT),
        (".tsx", Language.TYPESCRIPT),
        (".go", Language.GO),
        (".rs", Language.RUST),
        (".java", Language.JAVA),
        (".unknown", Language.UNKNOWN),
    ])
    def test_language_from_extension(self, ext, expected):
        """Language.from_extension maps correctly."""
        assert Language.from_extension(ext) == expected

    @pytest.mark.parametrize("ext,expected", [
        (".md", DocFormat.MARKDOWN),
        (".markdown", DocFormat.MARKDOWN),
        (".rst", DocFormat.RST),
        (".adoc", DocFormat.ASCIIDOC),
        (".txt", DocFormat.PLAIN),
        (".unknown", DocFormat.PLAIN),
    ])
    def test_docformat_from_extension(self, ext, expected):
        """DocFormat.from_extension maps correctly."""
        assert DocFormat.from_extension(ext) == expected
