"""Tests for git command functions."""

import pytest
from pathlib import Path
import tempfile
import subprocess

from docwatch.git.commands import (
    GitCommandError,
    Commit,
    ChangedFile,
    run_git_command,
    get_current_branch,
    get_recent_commits,
    get_changed_files,
    get_file_diff,
    get_file_at_commit,
    _is_valid_commit_hash,
    _parse_numstat_output,
    _parse_name_status_output,
)


@pytest.fixture
def temp_git_repo():
    """Create a temporary git repository with some commits."""
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

        # Create initial commit
        (repo_path / 'README.md').write_text('# Test Project\n')
        subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Initial commit'],
            cwd=repo_path, capture_output=True
        )

        # Create second commit with a Python file
        (repo_path / 'main.py').write_text('def hello():\n    print("Hello")\n')
        subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Add main.py'],
            cwd=repo_path, capture_output=True
        )

        # Create third commit modifying existing file
        (repo_path / 'main.py').write_text(
            'def hello():\n    print("Hello, World!")\n\ndef goodbye():\n    print("Bye")\n'
        )
        subprocess.run(['git', 'add', '.'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Update main.py with goodbye'],
            cwd=repo_path, capture_output=True
        )

        yield repo_path


@pytest.fixture
def empty_git_repo():
    """Create a git repository with no commits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir)
        subprocess.run(['git', 'init'], cwd=repo_path, capture_output=True)
        subprocess.run(
            ['git', 'config', 'user.email', 'test@example.com'],
            cwd=repo_path, capture_output=True
        )
        subprocess.run(
            ['git', 'config', 'user.name', 'Test User'],
            cwd=repo_path, capture_output=True
        )
        yield repo_path


class TestIsValidCommitHash:
    def test_valid_full_sha(self):
        assert _is_valid_commit_hash('abc123def456') is True

    def test_valid_head(self):
        assert _is_valid_commit_hash('HEAD') is True

    def test_valid_branch_name(self):
        assert _is_valid_commit_hash('main') is True
        assert _is_valid_commit_hash('feature/test') is True

    def test_invalid_empty(self):
        assert _is_valid_commit_hash('') is False

    def test_invalid_with_spaces(self):
        assert _is_valid_commit_hash('abc 123') is False

    def test_invalid_with_shell_chars(self):
        assert _is_valid_commit_hash('abc;rm -rf') is False
        assert _is_valid_commit_hash('$(whoami)') is False
        assert _is_valid_commit_hash('abc|cat') is False


class TestRunGitCommand:
    def test_successful_command(self, temp_git_repo):
        output = run_git_command(['status'], temp_git_repo)
        assert 'On branch' in output

    def test_invalid_command_raises(self, temp_git_repo):
        with pytest.raises(GitCommandError, match='Git command failed'):
            run_git_command(['invalid-command-xyz'], temp_git_repo)

    def test_nonexistent_repo_raises(self):
        with pytest.raises(GitCommandError):
            run_git_command(['status'], Path('/nonexistent/path'))


class TestGetCurrentBranch:
    def test_returns_branch_name(self, temp_git_repo):
        branch = get_current_branch(temp_git_repo)
        # Could be 'main' or 'master' depending on git config
        assert branch in ('main', 'master')

    def test_detached_head_returns_none(self, temp_git_repo):
        # Checkout a specific commit to enter detached HEAD
        commits = get_recent_commits(temp_git_repo)
        subprocess.run(
            ['git', 'checkout', commits[0].hash],
            cwd=temp_git_repo, capture_output=True
        )
        branch = get_current_branch(temp_git_repo)
        assert branch is None


class TestGetRecentCommits:
    def test_returns_commits(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        assert len(commits) == 3

    def test_returns_commit_objects(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=1)
        commit = commits[0]
        assert isinstance(commit, Commit)

    def test_commit_structure(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=1)
        commit = commits[0]
        assert len(commit.hash) == 40  # Full SHA
        assert commit.author == 'Test User'
        assert commit.date  # ISO format date
        assert commit.message == 'Update main.py with goodbye'

    def test_commit_order(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        # Most recent first
        assert commits[0].message == 'Update main.py with goodbye'
        assert commits[1].message == 'Add main.py'
        assert commits[2].message == 'Initial commit'

    def test_count_limits_results(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=2)
        assert len(commits) == 2

    def test_empty_repo_returns_empty_list(self, empty_git_repo):
        commits = get_recent_commits(empty_git_repo)
        assert commits == []

    def test_handles_pipe_in_author_name(self, temp_git_repo):
        """Ensure pipe characters in metadata don't break parsing."""
        # Create commit with pipe in author name
        subprocess.run(
            ['git', 'config', 'user.name', 'Test|User|Pipes'],
            cwd=temp_git_repo, capture_output=True
        )
        (temp_git_repo / 'test.txt').write_text('test')
        subprocess.run(['git', 'add', '.'], cwd=temp_git_repo, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Test with pipe|in|message'],
            cwd=temp_git_repo, capture_output=True
        )

        commits = get_recent_commits(temp_git_repo, count=1)
        assert commits[0].author == 'Test|User|Pipes'
        assert commits[0].message == 'Test with pipe|in|message'


class TestParseNumstatOutput:
    def test_normal_file(self):
        output = "10\t5\tsrc/main.py\n"
        result = _parse_numstat_output(output)
        assert result == {'src/main.py': (10, 5)}

    def test_binary_file(self):
        output = "-\t-\timage.png\n"
        result = _parse_numstat_output(output)
        assert result == {'image.png': (0, 0)}

    def test_full_rename(self):
        output = "0\t0\told.py => new.py\n"
        result = _parse_numstat_output(output)
        assert result == {'new.py': (0, 0)}

    def test_partial_rename(self):
        output = "10\t5\tsrc/{old => new}/file.py\n"
        result = _parse_numstat_output(output)
        assert result == {'src/new/file.py': (10, 5)}


class TestGetChangedFiles:
    def test_added_file(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        # "Add main.py" commit
        add_commit = commits[1]
        changed = get_changed_files(temp_git_repo, add_commit.hash)

        assert len(changed) == 1
        assert isinstance(changed[0], ChangedFile)
        assert changed[0].path == 'main.py'
        assert changed[0].status == 'added'
        assert changed[0].additions == 2
        assert changed[0].deletions == 0

    def test_modified_file(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        # "Update main.py with goodbye" commit
        update_commit = commits[0]
        changed = get_changed_files(temp_git_repo, update_commit.hash)

        assert len(changed) == 1
        assert changed[0].path == 'main.py'
        assert changed[0].status == 'modified'
        assert changed[0].additions > 0

    def test_initial_commit(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        initial_commit = commits[2]
        changed = get_changed_files(temp_git_repo, initial_commit.hash)

        assert len(changed) == 1
        assert changed[0].path == 'README.md'
        assert changed[0].status == 'added'

    def test_invalid_commit_hash_raises(self, temp_git_repo):
        with pytest.raises(ValueError, match='Invalid commit hash'):
            get_changed_files(temp_git_repo, 'abc;rm -rf /')

    def test_renamed_file(self, temp_git_repo):
        # Create a rename
        subprocess.run(
            ['git', 'mv', 'main.py', 'app.py'],
            cwd=temp_git_repo, capture_output=True
        )
        subprocess.run(['git', 'add', '.'], cwd=temp_git_repo, capture_output=True)
        subprocess.run(
            ['git', 'commit', '-m', 'Rename main to app'],
            cwd=temp_git_repo, capture_output=True
        )

        commits = get_recent_commits(temp_git_repo, count=1)
        changed = get_changed_files(temp_git_repo, commits[0].hash)

        assert len(changed) == 1
        assert changed[0].path == 'app.py'
        assert changed[0].old_path == 'main.py'
        assert changed[0].status == 'renamed'


class TestGetFileDiff:
    def test_returns_diff_content(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        update_commit = commits[0]
        diff = get_file_diff(temp_git_repo, update_commit.hash, 'main.py')

        assert 'Hello, World!' in diff
        assert '+' in diff  # Diff shows additions

    def test_invalid_commit_hash_raises(self, temp_git_repo):
        with pytest.raises(ValueError, match='Invalid commit hash'):
            get_file_diff(temp_git_repo, 'abc def', 'main.py')


class TestGetCommit:
    def test_returns_commit_by_hash(self, temp_git_repo):
        from docwatch.git.commands import get_commit

        commits = get_recent_commits(temp_git_repo, count=1)
        commit_hash = commits[0].hash

        commit = get_commit(temp_git_repo, commit_hash)

        assert commit.hash == commit_hash
        assert commit.author == 'Test User'
        assert commit.message == 'Update main.py with goodbye'

    def test_returns_commit_by_short_hash(self, temp_git_repo):
        from docwatch.git.commands import get_commit

        commits = get_recent_commits(temp_git_repo, count=1)
        short_hash = commits[0].hash[:7]

        commit = get_commit(temp_git_repo, short_hash)

        assert commit.hash == commits[0].hash  # Returns full hash

    def test_returns_commit_by_head(self, temp_git_repo):
        from docwatch.git.commands import get_commit

        commit = get_commit(temp_git_repo, 'HEAD')

        assert len(commit.hash) == 40
        assert commit.message == 'Update main.py with goodbye'

    def test_nonexistent_commit_raises(self, temp_git_repo):
        from docwatch.git.commands import get_commit, GitCommandError

        with pytest.raises(GitCommandError):
            get_commit(temp_git_repo, 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef')

    def test_invalid_hash_raises_valueerror(self, temp_git_repo):
        from docwatch.git.commands import get_commit

        with pytest.raises(ValueError, match='Invalid commit hash'):
            get_commit(temp_git_repo, 'abc;rm -rf')


class TestGetFileAtCommit:
    def test_returns_file_contents(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        # Get main.py as it was after "Add main.py"
        add_commit = commits[1]
        content = get_file_at_commit(temp_git_repo, add_commit.hash, 'main.py')

        assert content is not None
        assert 'def hello()' in content
        assert 'goodbye' not in content  # Not added yet

    def test_file_not_found_returns_none(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        initial_commit = commits[2]
        # main.py didn't exist in initial commit
        content = get_file_at_commit(temp_git_repo, initial_commit.hash, 'main.py')
        assert content is None

    def test_returns_current_version(self, temp_git_repo):
        commits = get_recent_commits(temp_git_repo, count=10)
        latest_commit = commits[0]
        content = get_file_at_commit(temp_git_repo, latest_commit.hash, 'main.py')

        assert 'Hello, World!' in content
        assert 'goodbye' in content

    def test_invalid_commit_hash_raises(self, temp_git_repo):
        with pytest.raises(ValueError, match='Invalid commit hash'):
            get_file_at_commit(temp_git_repo, '$(whoami)', 'main.py')
