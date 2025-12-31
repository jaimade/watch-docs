"""
Higher-level change tracking and entity change detection.

This module builds on the low-level git commands to provide:
- Analyzed commits with file categorization (code vs docs)
- Entity-level change detection (what functions/classes changed)
- Lazy loading for expensive operations (diffs)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from functools import cached_property
from pathlib import Path
from typing import NamedTuple, Optional, Callable

logger = logging.getLogger(__name__)

from docwatch.git.commands import (
    Commit,
    ChangedFile,
    GitCommandError,
    run_git_command,
    get_recent_commits,
    get_commit,
    get_commits_since,
    get_commits_between,
    get_changed_files,
    get_file_diff,
    get_file_at_commit,
)
from docwatch.constants import CODE_EXTENSIONS, DOC_EXTENSIONS, LANGUAGE_EXTENSION_MAP
from docwatch.extractors.python_ast import extract_from_source
from docwatch.models import EntityType


class ChangeType(Enum):
    """Types of changes that can occur to a code entity."""
    ADDED = "added"
    DELETED = "deleted"
    SIGNATURE_CHANGED = "signature_changed"
    DOCSTRING_CHANGED = "docstring_changed"
    BODY_CHANGED = "body_changed"


class EntitySnapshot(NamedTuple):
    """
    A snapshot of a code entity's key attributes at a point in time.

    Used for comparing entities between commits to detect changes.
    Using NamedTuple instead of raw tuple provides:
    - Named field access (snapshot.signature vs snapshot[0])
    - Type safety
    - Self-documenting code
    """
    signature: Optional[str]
    docstring: Optional[str]
    entity_type: EntityType


def _classify_file(path: str) -> tuple[bool, bool, Optional[str]]:
    """
    Classify a file path as code, documentation, or neither.

    Returns:
        Tuple of (is_code, is_doc, language)
        language is None for non-code files or unsupported languages.
    """
    suffix = Path(path).suffix.lower()
    is_code = suffix in CODE_EXTENSIONS
    is_doc = suffix in DOC_EXTENSIONS
    language = LANGUAGE_EXTENSION_MAP.get(suffix) if is_code else None
    return is_code, is_doc, language


@dataclass(frozen=True)
class AnalyzedChange:
    """
    A file change enriched with classification and optional diff.

    Wraps ChangedFile rather than duplicating its fields.
    Frozen for immutability - the diff is loaded lazily via cached_property.
    """
    file: ChangedFile
    is_code: bool = False
    is_doc: bool = False
    language: Optional[str] = None  # 'python', 'javascript', etc. for code files
    _diff_loader: Optional[Callable[[], str]] = field(
        default=None, repr=False, compare=False, hash=False
    )

    @property
    def path(self) -> str:
        """Convenience accessor for file path."""
        return self.file.path

    @property
    def status(self) -> str:
        """Convenience accessor for change status."""
        return self.file.status

    @cached_property
    def diff(self) -> Optional[str]:
        """
        Get the diff content, loading lazily on first access.

        The result is cached - subsequent accesses return the same value.
        Returns None if no diff loader was configured.
        """
        if self._diff_loader is not None:
            return self._diff_loader()
        return None


@dataclass
class AnalyzedCommit:
    """
    A commit with fully analyzed changes.

    Wraps the git-level Commit and adds:
    - Classified file changes
    - Properties for filtering by file type
    """
    commit: Commit
    changes: list[AnalyzedChange] = field(default_factory=list)

    @property
    def hash(self) -> str:
        return self.commit.hash

    @property
    def author(self) -> str:
        return self.commit.author

    @property
    def date(self) -> str:
        return self.commit.date

    @property
    def message(self) -> str:
        return self.commit.message

    @property
    def code_changes(self) -> list[AnalyzedChange]:
        """Get only changes to code files."""
        return [c for c in self.changes if c.is_code]

    @property
    def doc_changes(self) -> list[AnalyzedChange]:
        """Get only changes to documentation files."""
        return [c for c in self.changes if c.is_doc]

    @property
    def has_code_changes(self) -> bool:
        return any(c.is_code for c in self.changes)

    @property
    def has_doc_changes(self) -> bool:
        return any(c.is_doc for c in self.changes)


@dataclass
class EntityChange:
    """
    A change to a specific code entity (function, class, method, etc.).

    Captures what entity changed and how it changed between commits.
    """
    entity_name: str
    entity_type: EntityType
    file_path: str
    change_type: ChangeType
    old_signature: Optional[str] = None
    new_signature: Optional[str] = None
    old_docstring: Optional[str] = None
    new_docstring: Optional[str] = None


class ChangeTracker:
    """
    Track and analyze changes in a git repository.

    Provides high-level methods for:
    - Getting analyzed commits with file classification
    - Detecting entity-level changes in Python files
    """

    def __init__(self, repo_path: Path, validate: bool = True):
        """
        Initialize the change tracker.

        Args:
            repo_path: Path to the git repository root
            validate: If True, verify repo_path is a valid git repository

        Raises:
            ValueError: If repo_path doesn't exist or isn't a directory
            GitCommandError: If repo_path is not a git repository
        """
        if not repo_path.exists():
            raise ValueError(f"Path does not exist: {repo_path}")
        if not repo_path.is_dir():
            raise ValueError(f"Path is not a directory: {repo_path}")

        if validate:
            # Verify it's a git repository
            try:
                run_git_command(['rev-parse', '--git-dir'], repo_path)
            except GitCommandError as e:
                raise GitCommandError(
                    f"Not a git repository: {repo_path}"
                ) from e

        self.repo_path = repo_path

    def get_recent_changes(
        self,
        count: int = 10,
        include_diffs: bool = False
    ) -> list[AnalyzedCommit]:
        """
        Get recent commits with analyzed changes.

        Args:
            count: Maximum number of commits to return
            include_diffs: Whether to load diffs (can be slow)

        Returns:
            List of AnalyzedCommit objects, most recent first
        """
        commits = get_recent_commits(self.repo_path, count)
        return [self._analyze_commit(c, include_diffs) for c in commits]

    def get_changes_since(
        self,
        since: str,
        include_diffs: bool = False
    ) -> list[AnalyzedCommit]:
        """
        Get commits since a specific date/time.

        Args:
            since: Date string ('2024-01-01', '1 week ago', etc.)
            include_diffs: Whether to load diffs

        Returns:
            List of AnalyzedCommit objects
        """
        commits = get_commits_since(self.repo_path, since)
        return [self._analyze_commit(c, include_diffs) for c in commits]

    def get_changes_between(
        self,
        old_ref: str,
        new_ref: str = 'HEAD',
        include_diffs: bool = False
    ) -> list[AnalyzedCommit]:
        """
        Get commits between two git references.

        Args:
            old_ref: Starting reference (exclusive)
            new_ref: Ending reference (inclusive)
            include_diffs: Whether to load diffs

        Returns:
            List of AnalyzedCommit objects
        """
        commits = get_commits_between(self.repo_path, old_ref, new_ref)
        return [self._analyze_commit(c, include_diffs) for c in commits]

    def analyze_commit(
        self,
        commit_hash: str,
        include_diffs: bool = True
    ) -> AnalyzedCommit:
        """
        Fully analyze a single commit.

        Args:
            commit_hash: The commit to analyze (hash, branch, tag, or reference)
            include_diffs: Whether to load diffs (default True for single commit)

        Returns:
            AnalyzedCommit with full change details

        Raises:
            GitCommandError: If the commit doesn't exist
            ValueError: If commit_hash is invalid
        """
        # Directly fetch the commit - raises GitCommandError if not found
        commit = get_commit(self.repo_path, commit_hash)
        return self._analyze_commit(commit, include_diffs)

    def detect_entity_changes(
        self,
        analyzed_commit: AnalyzedCommit
    ) -> list[EntityChange]:
        """
        Detect which code entities changed in a commit.

        Compares the AST before and after to find:
        - New functions/classes
        - Deleted functions/classes
        - Signature changes
        - Docstring changes

        Note:
            Currently only Python files are supported. JavaScript, TypeScript,
            Go, Rust, Java, and other languages are skipped. File-level changes
            are still tracked for all languages, but entity-level detection
            (individual functions/classes) requires Python.

        Args:
            analyzed_commit: The commit to analyze

        Returns:
            List of EntityChange objects describing what changed
        """
        changes: list[EntityChange] = []

        for change in analyzed_commit.code_changes:
            if change.language == 'python':
                entity_changes = self._compare_python_entities(
                    analyzed_commit.hash,
                    change
                )
                changes.extend(entity_changes)
            elif change.language:
                logger.debug(
                    "Skipping entity detection for %s (language: %s). "
                    "Only Python is currently supported.",
                    change.path,
                    change.language
                )

        return changes

    def _analyze_commit(
        self,
        commit: Commit,
        include_diffs: bool
    ) -> AnalyzedCommit:
        """
        Convert a raw Commit to an AnalyzedCommit with classified changes.
        """
        changed_files = get_changed_files(self.repo_path, commit.hash)
        analyzed_changes: list[AnalyzedChange] = []

        for cf in changed_files:
            is_code, is_doc, language = _classify_file(cf.path)

            # Create a lazy loader for the diff
            diff_loader = None
            if include_diffs:
                # Capture variables for closure
                commit_hash = commit.hash
                file_path = cf.path
                repo_path = self.repo_path
                diff_loader = lambda ch=commit_hash, fp=file_path, rp=repo_path: (
                    get_file_diff(rp, ch, fp)
                )

            analyzed_changes.append(AnalyzedChange(
                file=cf,
                is_code=is_code,
                is_doc=is_doc,
                language=language,
                _diff_loader=diff_loader,
            ))

        return AnalyzedCommit(commit=commit, changes=analyzed_changes)

    def _compare_python_entities(
        self,
        commit_hash: str,
        change: AnalyzedChange
    ) -> list[EntityChange]:
        """
        Compare Python file before and after commit to find entity changes.
        """
        file_path = change.path

        # Get file content before commit (parent)
        # First commit has no parent, so handle that gracefully
        try:
            old_content = get_file_at_commit(
                self.repo_path,
                f"{commit_hash}^",
                file_path
            )
        except GitCommandError:
            # No parent commit (first commit) or file didn't exist before
            old_content = None

        # Get file content at commit
        new_content = get_file_at_commit(
            self.repo_path,
            commit_hash,
            file_path
        )

        # Parse both versions into snapshots
        old_entities: dict[str, EntitySnapshot] = {}
        new_entities: dict[str, EntitySnapshot] = {}

        if old_content:
            entities, _ = extract_from_source(old_content, Path(file_path))
            for e in entities:
                key = f"{e.parent}.{e.name}" if e.parent else e.name
                old_entities[key] = EntitySnapshot(
                    signature=e.signature,
                    docstring=e.docstring,
                    entity_type=e.entity_type,
                )

        if new_content:
            entities, _ = extract_from_source(new_content, Path(file_path))
            for e in entities:
                key = f"{e.parent}.{e.name}" if e.parent else e.name
                new_entities[key] = EntitySnapshot(
                    signature=e.signature,
                    docstring=e.docstring,
                    entity_type=e.entity_type,
                )

        # Compare
        changes: list[EntityChange] = []
        old_names = set(old_entities.keys())
        new_names = set(new_entities.keys())

        # Added entities
        for name in new_names - old_names:
            new = new_entities[name]
            changes.append(EntityChange(
                entity_name=name,
                entity_type=new.entity_type,
                file_path=file_path,
                change_type=ChangeType.ADDED,
                new_signature=new.signature,
                new_docstring=new.docstring,
            ))

        # Deleted entities
        for name in old_names - new_names:
            old = old_entities[name]
            changes.append(EntityChange(
                entity_name=name,
                entity_type=old.entity_type,
                file_path=file_path,
                change_type=ChangeType.DELETED,
                old_signature=old.signature,
                old_docstring=old.docstring,
            ))

        # Modified entities - check each change type independently
        for name in old_names & new_names:
            old = old_entities[name]
            new = new_entities[name]

            if old.signature != new.signature:
                changes.append(EntityChange(
                    entity_name=name,
                    entity_type=new.entity_type,
                    file_path=file_path,
                    change_type=ChangeType.SIGNATURE_CHANGED,
                    old_signature=old.signature,
                    new_signature=new.signature,
                ))

            if old.docstring != new.docstring:
                changes.append(EntityChange(
                    entity_name=name,
                    entity_type=new.entity_type,
                    file_path=file_path,
                    change_type=ChangeType.DOCSTRING_CHANGED,
                    old_docstring=old.docstring,
                    new_docstring=new.docstring,
                ))

        return changes
