"""
Data models for representing code and documentation structures.

All models are immutable (frozen) dataclasses for safety and hashability.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, TypedDict

from docwatch.constants import (
    LANGUAGE_EXTENSION_MAP,
    DOC_FORMAT_EXTENSION_MAP,
    SOURCE_DIR_PREFIXES,
)


# TypedDicts for extractor return types
class HeaderInfo(TypedDict):
    """A header extracted from documentation."""
    level: int
    text: str
    line: int


class CodeBlockInfo(TypedDict):
    """A code block extracted from documentation."""
    language: str
    code: str
    start_line: int
    end_line: int


class LinkInfo(TypedDict):
    """A link extracted from documentation."""
    text: str
    url: str
    line: int


def file_path_to_module_path(file_path: Path) -> str:
    """
    Convert a file path to a Python module-style path.

    Strips common source directory prefixes (configurable via
    SOURCE_DIR_PREFIXES in constants.py) to produce clean module paths.

    Examples:
        src/mypackage/module.py -> mypackage.module
        lib/utils/helper.py -> utils.helper
        app/models/user.py -> models.user

    Args:
        file_path: Path to a source file

    Returns:
        Dot-separated module path string
    """
    parts = list(file_path.with_suffix("").parts)

    # Remove common source directory prefixes
    for prefix in SOURCE_DIR_PREFIXES:
        if prefix in parts:
            parts = parts[parts.index(prefix) + 1:]
            break

    return ".".join(parts) if parts else file_path.stem


class Language(Enum):
    """Supported programming languages."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    PHP = "php"
    RUBY = "ruby"
    UNKNOWN = "unknown"

    @classmethod
    def from_extension(cls, ext: str) -> "Language":
        """Map file extension to language."""
        lang_str = LANGUAGE_EXTENSION_MAP.get(ext.lower())
        if lang_str:
            return cls(lang_str)
        return cls.UNKNOWN


class DocFormat(Enum):
    """Supported documentation formats."""
    MARKDOWN = "markdown"
    RST = "restructuredtext"
    ASCIIDOC = "asciidoc"
    PLAIN = "plain"

    @classmethod
    def from_extension(cls, ext: str) -> "DocFormat":
        """Map file extension to doc format."""
        format_str = DOC_FORMAT_EXTENSION_MAP.get(ext.lower())
        if format_str:
            return cls(format_str)
        return cls.PLAIN


class EntityType(Enum):
    """Types of code entities."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"
    MODULE = "module"


class ReferenceType(Enum):
    """Types of documentation references."""
    INLINE_CODE = "inline_code"
    CODE_BLOCK = "code_block"
    LINK = "link"
    HEADER = "header"


class LinkType(Enum):
    """Types of links between code and documentation."""
    EXACT = "exact"
    QUALIFIED = "qualified"
    PARTIAL = "partial"


@dataclass(frozen=True)
class Location:
    """A specific location in a file. Immutable and hashable."""
    file: Path
    line_start: int
    line_end: Optional[int] = None

    def __str__(self) -> str:
        if self.line_end and self.line_end != self.line_start:
            return f"{self.file}:{self.line_start}-{self.line_end}"
        return f"{self.file}:{self.line_start}"

    @property
    def span(self) -> int:
        """Number of lines this location spans."""
        if self.line_end:
            return self.line_end - self.line_start + 1
        return 1

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "file": str(self.file),
            "line_start": self.line_start,
            "line_end": self.line_end,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Location":
        """Reconstruct from dictionary."""
        return cls(
            file=Path(data["file"]),
            line_start=data["line_start"],
            line_end=data.get("line_end"),
        )

    @classmethod
    def from_str(cls, location_str: str) -> Optional["Location"]:
        """
        Parse a location string back into a Location object.

        Handles formats produced by __str__:
        - "path/to/file.py:42" -> Location(file, 42, None)
        - "path/to/file.py:42-50" -> Location(file, 42, 50)
        - "C:\\path\\file.py:42" -> Windows paths work via rsplit

        Returns None if the string cannot be parsed.
        """
        if ":" not in location_str:
            return None

        # Split from right to handle Windows paths (C:\path\file.py:42)
        parts = location_str.rsplit(":", 1)
        if len(parts) != 2:
            return None

        file_path, line_part = parts

        # Parse line numbers (could be "42" or "42-50")
        try:
            if "-" in line_part:
                start_str, end_str = line_part.split("-", 1)
                line_start = int(start_str)
                line_end = int(end_str)
            else:
                line_start = int(line_part)
                line_end = None
        except ValueError:
            return None

        return cls(
            file=Path(file_path),
            line_start=line_start,
            line_end=line_end,
        )


@dataclass(frozen=True)
class CodeEntity:
    """A named entity in code. Immutable and hashable."""
    name: str
    entity_type: EntityType
    location: Location
    signature: Optional[str] = None
    docstring: Optional[str] = None
    parent: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.entity_type.value}:{self.display_name}"

    @property
    def display_name(self) -> str:
        """Human-readable name with parent if applicable."""
        if self.parent:
            return f"{self.parent}.{self.name}"
        return self.name

    @property
    def module_path(self) -> str:
        """
        Convert file path to module-style path.

        See file_path_to_module_path() for details on prefix stripping.
        """
        return file_path_to_module_path(self.location.file)

    @property
    def qualified_name(self) -> str:
        """Full module.name style identifier."""
        base = f"{self.module_path}.{self.name}"
        if self.parent:
            return f"{self.module_path}.{self.parent}.{self.name}"
        return base

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "name": self.name,
            "type": self.entity_type.value,
            "location": self.location.to_dict(),
            "signature": self.signature,
            "docstring": self.docstring,
            "parent": self.parent,
            "qualified_name": self.qualified_name,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CodeEntity":
        """Reconstruct from dictionary."""
        return cls(
            name=data["name"],
            entity_type=EntityType(data["type"]),
            location=Location.from_dict(data["location"]),
            signature=data.get("signature"),
            docstring=data.get("docstring"),
            parent=data.get("parent"),
        )


@dataclass(frozen=True)
class DocReference:
    """A reference to code found in documentation. Immutable and hashable."""
    text: str
    location: Location
    reference_type: ReferenceType
    context: Optional[str] = None

    def __str__(self) -> str:
        return f"ref:{self.clean_text}@{self.location}"

    @property
    def clean_text(self) -> str:
        """Text with formatting removed."""
        return self.text.strip("`'\"[]")

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "text": self.text,
            "clean_text": self.clean_text,
            "location": self.location.to_dict(),
            "type": self.reference_type.value,
            "context": self.context,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DocReference":
        """Reconstruct from dictionary."""
        return cls(
            text=data["text"],
            location=Location.from_dict(data["location"]),
            reference_type=ReferenceType(data["type"]),
            context=data.get("context"),
        )


@dataclass(frozen=True)
class CodeDocLink:
    """A verified link between code and documentation. Immutable and hashable."""
    entity: CodeEntity
    reference: DocReference
    link_type: LinkType
    confidence: float

    def __str__(self) -> str:
        return f"{self.entity.name} <- {self.reference.clean_text} [{self.link_type.value}, {self.confidence:.0%}]"

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "entity": self.entity.to_dict(),
            "reference": self.reference.to_dict(),
            "link_type": self.link_type.value,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CodeDocLink":
        """Reconstruct from dictionary."""
        return cls(
            entity=CodeEntity.from_dict(data["entity"]),
            reference=DocReference.from_dict(data["reference"]),
            link_type=LinkType(data["link_type"]),
            confidence=data["confidence"],
        )


@dataclass
class CodeFile:
    """A parsed code file. Mutable to allow building up entities."""
    path: Path
    language: Language
    entities: list[CodeEntity] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return f"CodeFile({self.path}, {len(self.entities)} entities)"

    @property
    def functions(self) -> list[CodeEntity]:
        """All function entities."""
        return [e for e in self.entities if e.entity_type == EntityType.FUNCTION]

    @property
    def classes(self) -> list[CodeEntity]:
        """All class entities."""
        return [e for e in self.entities if e.entity_type == EntityType.CLASS]

    @property
    def entity_names(self) -> frozenset[str]:
        """Set of all entity names."""
        return frozenset(e.name for e in self.entities)

    def get_entity(self, name: str) -> Optional[CodeEntity]:
        """Get entity by name."""
        for entity in self.entities:
            if entity.name == name:
                return entity
        return None

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "path": str(self.path),
            "language": self.language.value,
            "entities": [e.to_dict() for e in self.entities],
            "imports": self.imports,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CodeFile":
        """Reconstruct from dictionary."""
        return cls(
            path=Path(data["path"]),
            language=Language(data["language"]),
            entities=[CodeEntity.from_dict(e) for e in data.get("entities", [])],
            imports=data.get("imports", []),
        )


@dataclass
class DocFile:
    """A parsed documentation file. Mutable to allow building up references."""
    path: Path
    format: DocFormat
    title: Optional[str] = None
    references: list[DocReference] = field(default_factory=list)
    headers: list[dict] = field(default_factory=list)

    def __str__(self) -> str:
        return f"DocFile({self.path}, {len(self.references)} refs)"

    @property
    def referenced_names(self) -> frozenset[str]:
        """Set of all referenced code names."""
        return frozenset(r.clean_text for r in self.references)

    def to_dict(self) -> dict:
        """JSON-serializable representation."""
        return {
            "path": str(self.path),
            "format": self.format.value,
            "title": self.title,
            "references": [r.to_dict() for r in self.references],
            "headers": self.headers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DocFile":
        """Reconstruct from dictionary."""
        return cls(
            path=Path(data["path"]),
            format=DocFormat(data["format"]),
            title=data.get("title"),
            references=[DocReference.from_dict(r) for r in data.get("references", [])],
            headers=data.get("headers", []),
        )
