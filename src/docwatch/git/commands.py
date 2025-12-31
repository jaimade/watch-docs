"""Low-level Git command execution and parsing."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class GitCommandError(Exception):
    """Raised when a git command fails."""
    pass


class GitParseError(Exception):
    """Raised when git output cannot be parsed."""
    pass


@dataclass(frozen=True)
class Commit:
    """Represents a git commit."""
    hash: str
    author: str
    date: str
    message: str


@dataclass(frozen=True)
class ChangedFile:
    """Represents a file changed in a commit."""
    path: str
    status: str  # 'added', 'modified', 'deleted', 'renamed', 'copied', 'type_changed'
    additions: int
    deletions: int
    old_path: Optional[str] = None  # Only set for renames


# Module-level constants
_STATUS_MAP: dict[str, str] = {
    'A': 'added',
    'M': 'modified',
    'D': 'deleted',
    'R': 'renamed',
    'C': 'copied',
    'T': 'type_changed',
}

# Null byte delimiter - cannot appear in git metadata
# Use %x00 in git format strings, actual \x00 for parsing output
_NULL_FORMAT = '%x00'  # For git --format strings
_NULL = '\x00'         # For parsing output


def run_git_command(args: list[str], cwd: Path, timeout: int = 30) -> str:
    """
    Run a git command and return output.

    Args:
        args: Command arguments, e.g., ['log', '--oneline', '-n', '10']
        cwd: Directory to run command in
        timeout: Maximum seconds to wait

    Returns:
        Command stdout

    Raises:
        GitCommandError: If command fails
    """
    try:
        result = subprocess.run(
            ['git'] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if result.returncode != 0:
            raise GitCommandError(f"Git command failed: {result.stderr.strip()}")

        return result.stdout

    except subprocess.TimeoutExpired:
        raise GitCommandError(f"Git command timed out after {timeout}s")
    except FileNotFoundError:
        raise GitCommandError("Git is not installed or not in PATH")


def _is_valid_commit_hash(commit_hash: str) -> bool:
    """Check if a string looks like a valid git commit reference."""
    if not commit_hash or not isinstance(commit_hash, str):
        return False

    # Whitelist approach: only allow characters valid in git references
    # - Alphanumeric (SHA hashes, branch names, tags)
    # - Path separators and naming: / - _ .
    # - Reference modifiers: ^ ~ @ { } (e.g., HEAD~3, main@{1})
    allowed = set(
        'abcdefghijklmnopqrstuvwxyz'
        'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
        '0123456789'
        '/_-.^~@{}'
    )

    # Length limit prevents abuse
    if len(commit_hash) > 256:
        return False

    return all(c in allowed for c in commit_hash)


def get_current_branch(repo_path: Path) -> Optional[str]:
    """
    Get the current branch name.

    Returns:
        Branch name, or None if in detached HEAD state.
    """
    output = run_git_command(['branch', '--show-current'], repo_path)
    branch = output.strip()
    return branch if branch else None


def get_recent_commits(repo_path: Path, count: int = 10) -> list[Commit]:
    """
    Get recent commits with metadata.

    Args:
        repo_path: Path to the git repository
        count: Maximum number of commits to return

    Returns:
        List of Commit objects, most recent first.
        Empty list if repository has no commits.
    """
    # Use null byte delimiter - safe because it can't appear in git fields
    # %x00 is git's escape for null byte in format strings
    format_str = f'%H{_NULL_FORMAT}%an{_NULL_FORMAT}%aI{_NULL_FORMAT}%s{_NULL_FORMAT}'

    try:
        output = run_git_command(
            ['log', f'-n{count}', f'--format={format_str}'],
            repo_path
        )
    except GitCommandError as e:
        # Empty repository has no commits
        if 'does not have any commits' in str(e):
            return []
        raise

    commits = []
    # Split by null byte, then clean up whitespace from each field
    entries = [e.strip() for e in output.split(_NULL) if e.strip()]

    # Process in groups of 4 (hash, author, date, message)
    for i in range(0, len(entries) - 3, 4):
        commits.append(Commit(
            hash=entries[i],
            author=entries[i + 1],
            date=entries[i + 2],
            message=entries[i + 3],
        ))

    return commits


def _parse_numstat_output(output: str) -> dict[str, tuple[int, int]]:
    """
    Parse git numstat output into a path -> (additions, deletions) map.

    Handles:
        - Normal files: "10\t5\tpath/file.py"
        - Binary files: "-\t-\tpath/image.png"
        - Renames: "10\t5\t{old => new}/file.py" or "old.py => new.py"
    """
    stats: dict[str, tuple[int, int]] = {}

    for line in output.strip().split('\n'):
        if not line:
            continue

        parts = line.split('\t')
        if len(parts) < 3:
            continue

        adds_str, dels_str = parts[0], parts[1]
        filepath = parts[2]

        # Handle rename syntax in numstat
        if '=>' in filepath:
            # Could be "{prefix/old => prefix/new}/suffix" or "old.py => new.py"
            if '{' in filepath:
                # Partial rename: extract new path
                before_brace = filepath.split('{')[0]
                inside_brace = filepath.split('{')[1].split('}')[0]
                after_brace = filepath.split('}')[1] if '}' in filepath else ''
                new_part = inside_brace.split('=>')[1].strip()
                filepath = before_brace + new_part + after_brace
            else:
                # Full rename: "old.py => new.py"
                filepath = filepath.split('=>')[1].strip()

        # Binary files show "-" for stats
        additions = 0 if adds_str == '-' else int(adds_str)
        deletions = 0 if dels_str == '-' else int(dels_str)
        stats[filepath] = (additions, deletions)

    return stats


def _parse_name_status_output(
    output: str,
    stats: dict[str, tuple[int, int]]
) -> list[ChangedFile]:
    """
    Parse git name-status output and combine with numstat data.

    Handles:
        - Normal: "M\tpath/file.py"
        - Rename: "R100\told.py\tnew.py"
    """
    changed_files = []

    for line in output.strip().split('\n'):
        if not line:
            continue

        parts = line.split('\t')
        if len(parts) < 2:
            continue

        status_code = parts[0][0]  # First char (R100 -> R)
        status = _STATUS_MAP.get(status_code, 'unknown')

        if status_code in ('R', 'C') and len(parts) >= 3:
            # Rename/Copy: status, old_path, new_path
            old_path, new_path = parts[1], parts[2]
            additions, deletions = stats.get(new_path, (0, 0))
            changed_files.append(ChangedFile(
                path=new_path,
                status=status,
                additions=additions,
                deletions=deletions,
                old_path=old_path,
            ))
        else:
            filepath = parts[1]
            additions, deletions = stats.get(filepath, (0, 0))
            changed_files.append(ChangedFile(
                path=filepath,
                status=status,
                additions=additions,
                deletions=deletions,
            ))

    return changed_files


def get_changed_files(repo_path: Path, commit_hash: str) -> list[ChangedFile]:
    """
    Get files changed in a specific commit.

    Args:
        repo_path: Path to the git repository
        commit_hash: The commit hash or reference (HEAD, branch name, etc.)

    Returns:
        List of ChangedFile objects describing each changed file.

    Raises:
        GitCommandError: If the commit doesn't exist or git fails
        ValueError: If commit_hash is invalid
    """
    if not _is_valid_commit_hash(commit_hash):
        raise ValueError(f"Invalid commit hash: {commit_hash!r}")

    # Get additions/deletions with numstat
    numstat_output = run_git_command(
        ['show', '--numstat', '--format=', commit_hash],
        repo_path
    )
    stats = _parse_numstat_output(numstat_output)

    # Get status codes with name-status
    status_output = run_git_command(
        ['show', '--name-status', '--format=', commit_hash],
        repo_path
    )

    return _parse_name_status_output(status_output, stats)


def get_file_diff(repo_path: Path, commit_hash: str, file_path: str) -> str:
    """
    Get the diff for a specific file in a commit.

    Args:
        repo_path: Path to the git repository
        commit_hash: The commit to get the diff from
        file_path: Path to the file relative to repo root

    Returns:
        The diff content as a string

    Raises:
        GitCommandError: If the commit or file doesn't exist
        ValueError: If commit_hash is invalid
    """
    if not _is_valid_commit_hash(commit_hash):
        raise ValueError(f"Invalid commit hash: {commit_hash!r}")

    return run_git_command(
        ['show', '--format=', commit_hash, '--', file_path],
        repo_path
    )


def get_commit(repo_path: Path, commit_hash: str) -> Commit:
    """
    Get a single commit by its hash or reference.

    Args:
        repo_path: Path to the git repository
        commit_hash: The commit hash or reference (HEAD, branch, tag, etc.)

    Returns:
        Commit object with metadata

    Raises:
        GitCommandError: If the commit doesn't exist
        ValueError: If commit_hash is invalid
    """
    if not _is_valid_commit_hash(commit_hash):
        raise ValueError(f"Invalid commit hash: {commit_hash!r}")

    format_str = f'%H{_NULL_FORMAT}%an{_NULL_FORMAT}%aI{_NULL_FORMAT}%s'

    output = run_git_command(
        ['show', '-s', f'--format={format_str}', commit_hash],
        repo_path
    )

    parts = [p.strip() for p in output.split(_NULL)]
    if len(parts) < 4:
        raise GitCommandError(f"Unexpected git output for commit {commit_hash}")

    return Commit(
        hash=parts[0],
        author=parts[1],
        date=parts[2],
        message=parts[3],
    )


def get_commits_since(
    repo_path: Path,
    since: str,
    count: int = 100
) -> list[Commit]:
    """
    Get commits since a specific date or time.

    Args:
        repo_path: Path to the git repository
        since: Date string (e.g., '2024-01-01', '1 week ago', '2 hours ago')
        count: Maximum number of commits to return

    Returns:
        List of Commit objects, most recent first.
    """
    format_str = f'%H{_NULL_FORMAT}%an{_NULL_FORMAT}%aI{_NULL_FORMAT}%s{_NULL_FORMAT}'

    try:
        output = run_git_command(
            ['log', f'-n{count}', f'--since={since}', f'--format={format_str}'],
            repo_path
        )
    except GitCommandError as e:
        if 'does not have any commits' in str(e):
            return []
        raise

    if not output.strip():
        return []

    commits = []
    entries = [e.strip() for e in output.split(_NULL) if e.strip()]

    for i in range(0, len(entries) - 3, 4):
        commits.append(Commit(
            hash=entries[i],
            author=entries[i + 1],
            date=entries[i + 2],
            message=entries[i + 3],
        ))

    return commits


def get_commits_between(
    repo_path: Path,
    old_ref: str,
    new_ref: str = 'HEAD'
) -> list[Commit]:
    """
    Get commits between two git references.

    Args:
        repo_path: Path to the git repository
        old_ref: Starting reference (exclusive)
        new_ref: Ending reference (inclusive), defaults to HEAD

    Returns:
        List of Commit objects, most recent first.
    """
    if not _is_valid_commit_hash(old_ref):
        raise ValueError(f"Invalid git reference: {old_ref!r}")
    if not _is_valid_commit_hash(new_ref):
        raise ValueError(f"Invalid git reference: {new_ref!r}")

    format_str = f'%H{_NULL_FORMAT}%an{_NULL_FORMAT}%aI{_NULL_FORMAT}%s{_NULL_FORMAT}'

    try:
        output = run_git_command(
            ['log', f'{old_ref}..{new_ref}', f'--format={format_str}'],
            repo_path
        )
    except GitCommandError as e:
        if 'does not have any commits' in str(e):
            return []
        raise

    if not output.strip():
        return []

    commits = []
    entries = [e.strip() for e in output.split(_NULL) if e.strip()]

    for i in range(0, len(entries) - 3, 4):
        commits.append(Commit(
            hash=entries[i],
            author=entries[i + 1],
            date=entries[i + 2],
            message=entries[i + 3],
        ))

    return commits


def get_file_at_commit(
    repo_path: Path,
    commit_hash: str,
    file_path: str
) -> Optional[str]:
    """
    Get file contents as they were at a specific commit.

    Args:
        repo_path: Path to the git repository
        commit_hash: The commit to retrieve file from
        file_path: Path to the file relative to repo root

    Returns:
        File contents, or None if file didn't exist at that commit

    Raises:
        GitCommandError: If the commit doesn't exist or git fails unexpectedly
        ValueError: If commit_hash is invalid
    """
    if not _is_valid_commit_hash(commit_hash):
        raise ValueError(f"Invalid commit hash: {commit_hash!r}")

    try:
        return run_git_command(
            ['show', f'{commit_hash}:{file_path}'],
            repo_path
        )
    except GitCommandError as e:
        # Distinguish "file not found" from other errors
        # Git may say "does not exist" or "exists on disk, but not in <commit>"
        error_msg = str(e).lower()
        if ('does not exist' in error_msg or
            'not in' in error_msg or
            'bad revision' in error_msg):
            return None
        # Re-raise unexpected errors
        raise
