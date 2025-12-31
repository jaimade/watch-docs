"""Tests for the ChangeTracker and entity change detection."""

import pytest
from pathlib import Path
import tempfile
import subprocess

from docwatch.git.tracker import (
    ChangeType,
    AnalyzedChange,
    AnalyzedCommit,
    EntityChange,
    ChangeTracker,
    _classify_file,
)
from docwatch.git.commands import Commit, ChangedFile
from docwatch.models import EntityType


class TestClassifyFile:
    def test_python_is_code(self):
        is_code, is_doc, language = _classify_file('src/main.py')
        assert is_code is True
        assert is_doc is False
        assert language == 'python'

    def test_javascript_is_code(self):
        is_code, is_doc, language = _classify_file('app.js')
        assert is_code is True
        assert is_doc is False
        assert language == 'javascript'

    def test_typescript_is_code(self):
        is_code, is_doc, language = _classify_file('app.ts')
        assert is_code is True
        assert is_doc is False
        assert language == 'typescript'

    def test_markdown_is_doc(self):
        is_code, is_doc, language = _classify_file('README.md')
        assert is_code is False
        assert is_doc is True
        assert language is None

    def test_rst_is_doc(self):
        is_code, is_doc, language = _classify_file('docs/index.rst')
        assert is_code is False
        assert is_doc is True
        assert language is None

    def test_unknown_is_neither(self):
        is_code, is_doc, language = _classify_file('data.json')
        assert is_code is False
        assert is_doc is False
        assert language is None

    def test_code_without_language_mapping(self):
        """Code files without explicit language mapping return None for language."""
        is_code, is_doc, language = _classify_file('script.sh')
        assert is_code is True
        assert is_doc is False
        assert language is None  # Shell not in LANGUAGE_EXTENSION_MAP


class TestAnalyzedChange:
    def test_convenience_accessors(self):
        cf = ChangedFile(
            path='src/main.py',
            status='modified',
            additions=10,
            deletions=5
        )
        ac = AnalyzedChange(file=cf, is_code=True, is_doc=False)

        assert ac.path == 'src/main.py'
        assert ac.status == 'modified'

    def test_lazy_diff_loading(self):
        cf = ChangedFile(path='test.py', status='modified', additions=1, deletions=0)
        load_count = [0]

        def loader():
            load_count[0] += 1
            return 'diff content'

        ac = AnalyzedChange(file=cf, _diff_loader=loader)

        # Diff not loaded yet
        assert load_count[0] == 0

        # Access diff - should trigger load
        assert ac.diff == 'diff content'
        assert load_count[0] == 1

        # Access again - should use cached value
        assert ac.diff == 'diff content'
        assert load_count[0] == 1

    def test_no_diff_loader(self):
        cf = ChangedFile(path='test.py', status='modified', additions=1, deletions=0)
        ac = AnalyzedChange(file=cf)
        assert ac.diff is None


class TestAnalyzedCommit:
    def test_properties_delegate_to_commit(self):
        commit = Commit(
            hash='abc123',
            author='Test User',
            date='2024-01-15T10:30:00',
            message='Fix bug'
        )
        ac = AnalyzedCommit(commit=commit)

        assert ac.hash == 'abc123'
        assert ac.author == 'Test User'
        assert ac.date == '2024-01-15T10:30:00'
        assert ac.message == 'Fix bug'

    def test_code_changes_filter(self):
        commit = Commit(hash='abc', author='u', date='d', message='m')
        changes = [
            AnalyzedChange(
                file=ChangedFile(path='main.py', status='modified', additions=1, deletions=0),
                is_code=True
            ),
            AnalyzedChange(
                file=ChangedFile(path='README.md', status='modified', additions=1, deletions=0),
                is_doc=True
            ),
            AnalyzedChange(
                file=ChangedFile(path='app.js', status='added', additions=10, deletions=0),
                is_code=True
            ),
        ]
        ac = AnalyzedCommit(commit=commit, changes=changes)

        code_changes = ac.code_changes
        assert len(code_changes) == 2
        assert all(c.is_code for c in code_changes)

    def test_doc_changes_filter(self):
        commit = Commit(hash='abc', author='u', date='d', message='m')
        changes = [
            AnalyzedChange(
                file=ChangedFile(path='main.py', status='modified', additions=1, deletions=0),
                is_code=True
            ),
            AnalyzedChange(
                file=ChangedFile(path='README.md', status='modified', additions=1, deletions=0),
                is_doc=True
            ),
        ]
        ac = AnalyzedCommit(commit=commit, changes=changes)

        doc_changes = ac.doc_changes
        assert len(doc_changes) == 1
        assert doc_changes[0].path == 'README.md'

    def test_has_code_changes(self):
        commit = Commit(hash='abc', author='u', date='d', message='m')

        # With code changes
        ac_with_code = AnalyzedCommit(commit=commit, changes=[
            AnalyzedChange(
                file=ChangedFile(path='main.py', status='modified', additions=1, deletions=0),
                is_code=True
            ),
        ])
        assert ac_with_code.has_code_changes is True
        assert ac_with_code.has_doc_changes is False

        # Without code changes
        ac_without_code = AnalyzedCommit(commit=commit, changes=[
            AnalyzedChange(
                file=ChangedFile(path='README.md', status='modified', additions=1, deletions=0),
                is_doc=True
            ),
        ])
        assert ac_without_code.has_code_changes is False
        assert ac_without_code.has_doc_changes is True


@pytest.fixture
def tracker_repo():
    """Create a git repository with Python files for testing entity changes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)

        # Initialize repo
        subprocess.run(['git', 'init'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=repo_path, capture_output=True
        )

        # Initial commit with a Python file
        (repo_path / 'module.py').write_text('''
def greet(name):
    """Say hello to someone."""
    print(f"Hello, {name}!")

class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        return a + b
''')
        (repo_path / 'README.md').write_text('# Test Project\n')
        subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Initial commit'],
            cwd=repo_path, capture_output=True
        )

        # Second commit: add a function
        (repo_path / 'module.py').write_text('''
def greet(name):
    """Say hello to someone."""
    print(f"Hello, {name}!")

def farewell(name):
    """Say goodbye."""
    print(f"Goodbye, {name}!")

class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        return a + b
''')
        subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Add farewell function'],
            cwd=repo_path, capture_output=True
        )

        # Third commit: change signature
        (repo_path / 'module.py').write_text('''
def greet(name, formal: bool = False):
    """Say hello to someone."""
    prefix = "Dear" if formal else "Hello"
    print(f"{prefix}, {name}!")

def farewell(name):
    """Say goodbye."""
    print(f"Goodbye, {name}!")

class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
''')
        subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Add formal parameter and subtract method'],
            cwd=repo_path, capture_output=True
        )

        # Fourth commit: change BOTH signature AND docstring of farewell
        (repo_path / 'module.py').write_text('''
def greet(name, formal: bool = False):
    """Say hello to someone."""
    prefix = "Dear" if formal else "Hello"
    print(f"{prefix}, {name}!")

def farewell(name, wave: bool = True):
    """Say goodbye to someone, optionally with a wave."""
    print(f"Goodbye, {name}!")
    if wave:
        print("*waves*")

class Calculator:
    """A simple calculator."""

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
''')
        subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Update farewell with wave parameter and better docstring'],
            cwd=repo_path, capture_output=True
        )

        yield repo_path


class TestChangeTracker:
    def test_validates_path_exists(self):
        with pytest.raises(ValueError, match="Path does not exist"):
            ChangeTracker(Path("/nonexistent/path/to/repo"))

    def test_validates_path_is_directory(self, tmp_path):
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("hello")
        with pytest.raises(ValueError, match="Path is not a directory"):
            ChangeTracker(file_path)

    def test_validates_is_git_repo(self, tmp_path):
        # tmp_path is a directory but not a git repo
        from docwatch.git.commands import GitCommandError
        with pytest.raises(GitCommandError, match="Not a git repository"):
            ChangeTracker(tmp_path)

    def test_skip_validation(self, tmp_path):
        # Can skip validation if needed (e.g., for testing)
        tracker = ChangeTracker(tmp_path, validate=False)
        assert tracker.repo_path == tmp_path

    def test_get_recent_changes(self, tracker_repo):
        tracker = ChangeTracker(tracker_repo)
        changes = tracker.get_recent_changes(count=4)

        assert len(changes) == 4
        assert all(isinstance(c, AnalyzedCommit) for c in changes)

    def test_changes_are_classified(self, tracker_repo):
        tracker = ChangeTracker(tracker_repo)
        changes = tracker.get_recent_changes(count=1)

        # Most recent commit modified module.py
        assert len(changes) == 1
        commit = changes[0]
        assert commit.has_code_changes is True

        code_changes = commit.code_changes
        assert len(code_changes) == 1
        assert code_changes[0].path == 'module.py'
        assert code_changes[0].is_code is True

    def test_detect_added_entity(self, tracker_repo):
        tracker = ChangeTracker(tracker_repo)
        commits = tracker.get_recent_changes(count=4)

        # Find the "Add farewell function" commit (not "Update farewell...")
        farewell_commit = next(
            c for c in commits if c.message == 'Add farewell function'
        )

        entity_changes = tracker.detect_entity_changes(farewell_commit)

        # Should detect added farewell function
        added = [e for e in entity_changes if e.change_type == ChangeType.ADDED]
        assert len(added) == 1
        assert added[0].entity_name == 'farewell'
        assert added[0].entity_type == EntityType.FUNCTION

    def test_detect_signature_change(self, tracker_repo):
        tracker = ChangeTracker(tracker_repo)
        commits = tracker.get_recent_changes(count=4)

        # Find the "Add formal parameter" commit
        formal_commit = next(
            c for c in commits if 'formal parameter' in c.message
        )

        entity_changes = tracker.detect_entity_changes(formal_commit)

        # Should detect greet signature change
        sig_changes = [e for e in entity_changes if e.change_type == ChangeType.SIGNATURE_CHANGED]
        greet_change = next((e for e in sig_changes if e.entity_name == 'greet'), None)

        assert greet_change is not None
        assert 'formal' in (greet_change.new_signature or '')
        assert 'formal' not in (greet_change.old_signature or '')

    def test_detect_added_method(self, tracker_repo):
        tracker = ChangeTracker(tracker_repo)
        commits = tracker.get_recent_changes(count=4)

        # Find the "Add formal parameter and subtract method" commit
        subtract_commit = next(
            c for c in commits if 'subtract' in c.message
        )

        entity_changes = tracker.detect_entity_changes(subtract_commit)

        # Should detect added subtract method
        added = [e for e in entity_changes if e.change_type == ChangeType.ADDED]
        subtract_change = next(
            (e for e in added if 'subtract' in e.entity_name), None
        )

        assert subtract_change is not None
        assert subtract_change.entity_type == EntityType.METHOD

    def test_detect_both_signature_and_docstring_change(self, tracker_repo):
        """Verify that both signature AND docstring changes are detected for same entity."""
        tracker = ChangeTracker(tracker_repo)
        commits = tracker.get_recent_changes(count=1)
        latest_commit = commits[0]  # "Update farewell with wave parameter and better docstring"

        entity_changes = tracker.detect_entity_changes(latest_commit)

        # Filter to just farewell changes
        farewell_changes = [e for e in entity_changes if e.entity_name == 'farewell']

        # Should have TWO changes: signature AND docstring
        assert len(farewell_changes) == 2

        change_types = {e.change_type for e in farewell_changes}
        assert ChangeType.SIGNATURE_CHANGED in change_types
        assert ChangeType.DOCSTRING_CHANGED in change_types

        # Verify the signature change
        sig_change = next(e for e in farewell_changes if e.change_type == ChangeType.SIGNATURE_CHANGED)
        assert 'wave' in (sig_change.new_signature or '')

        # Verify the docstring change
        doc_change = next(e for e in farewell_changes if e.change_type == ChangeType.DOCSTRING_CHANGED)
        assert 'optionally with a wave' in (doc_change.new_docstring or '')

    def test_include_diffs(self, tracker_repo):
        tracker = ChangeTracker(tracker_repo)
        commits = tracker.get_recent_changes(count=1, include_diffs=True)

        commit = commits[0]
        code_change = commit.code_changes[0]

        # Diff should be loaded
        assert code_change.diff is not None
        assert 'wave' in code_change.diff  # From the latest commit


class TestEntityChange:
    def test_entity_change_structure(self):
        change = EntityChange(
            entity_name='my_function',
            entity_type=EntityType.FUNCTION,
            file_path='module.py',
            change_type=ChangeType.SIGNATURE_CHANGED,
            old_signature='def my_function(a)',
            new_signature='def my_function(a, b)',
        )

        assert change.entity_name == 'my_function'
        assert change.entity_type == EntityType.FUNCTION
        assert change.file_path == 'module.py'
        assert change.change_type == ChangeType.SIGNATURE_CHANGED
        assert change.old_signature == 'def my_function(a)'
        assert change.new_signature == 'def my_function(a, b)'
