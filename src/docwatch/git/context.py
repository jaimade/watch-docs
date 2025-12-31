"""
Context managers for safe git operations.

These context managers ensure proper cleanup and state restoration
when working with git repositories, even if errors occur.

Error Handling Philosophy
-------------------------
On entry failure (clone fails, checkout fails, stash fails):
    Raises GitContextError immediately. No cleanup needed since
    the operation never started.

On exit/restore failure:
    - cloned_repo: Always cleans up temp directory (cleanup can't really fail)
    - checkout_commit: Issues RuntimeWarning, leaves repo at checked-out commit.
      Rationale: Force-restoring could lose work done during the context.
      User can manually checkout original branch.
    - stashed_changes: Issues RuntimeWarning, leaves changes in stash.
      Rationale: Better to preserve changes in stash than lose them.
      User can manually run 'git stash pop'.

The warning approach for restore failures prioritizes data preservation
over silent cleanup. Users see warnings and can recover manually.
"""

from __future__ import annotations

import shutil
import tempfile
import warnings
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from docwatch.git.commands import (
    run_git_command,
    get_current_branch,
    GitCommandError,
)

__all__ = [
    'GitContextError',
    'cloned_repo',
    'checkout_commit',
    'stashed_changes',
]


class GitContextError(Exception):
    """Raised when a git context manager operation fails."""


def _get_head_ref(repo_path: Path) -> str:
    """
    Get the current HEAD reference (branch name or commit hash).

    Returns branch name if on a branch, otherwise returns the commit hash.
    This allows restoring state even from detached HEAD.
    """
    branch = get_current_branch(repo_path)
    if branch:
        return branch
    # Detached HEAD - get the commit hash
    return run_git_command(['rev-parse', 'HEAD'], repo_path).strip()


def _has_uncommitted_changes(repo_path: Path) -> bool:
    """Check if the repository has uncommitted changes."""
    output = run_git_command(['status', '--porcelain'], repo_path)
    return bool(output.strip())


@contextmanager
def cloned_repo(
    repo_url: str,
    depth: Optional[int] = 1,
    branch: Optional[str] = None,
    timeout: int = 120,
) -> Generator[Path, None, None]:
    """
    Clone a repository to a temporary directory.

    The temporary directory is automatically cleaned up when the context exits,
    even if an error occurs.

    Args:
        repo_url: URL of the repository to clone
        depth: Clone depth (default 1 for shallow clone, None for full clone)
        branch: Specific branch to clone (default: repository's default branch)
        timeout: Maximum seconds to wait for clone (default 120)

    Yields:
        Path to the cloned repository

    Raises:
        GitContextError: If cloning fails

    Example:
        with cloned_repo('https://github.com/user/repo') as repo_path:
            tracker = ChangeTracker(repo_path)
            changes = tracker.get_recent_changes()
        # Cleanup happens automatically
    """
    # Create parent temp directory, clone into 'repo' subdirectory
    # This avoids cloning into an existing directory (git requires target to not exist)
    temp_parent = Path(tempfile.mkdtemp(prefix='docwatch_clone_'))
    repo_path = temp_parent / 'repo'

    try:
        # Build clone command
        clone_args = ['clone']
        if depth is not None:
            clone_args.extend(['--depth', str(depth)])
        if branch:
            clone_args.extend(['--branch', branch])
        clone_args.extend([repo_url, str(repo_path)])

        try:
            run_git_command(clone_args, Path.cwd(), timeout=timeout)
        except GitCommandError as e:
            raise GitContextError(f"Failed to clone {repo_url}: {e}") from e

        yield repo_path

    finally:
        # Always cleanup parent dir, ignore errors (e.g., permission issues on Windows)
        shutil.rmtree(temp_parent, ignore_errors=True)


@contextmanager
def checkout_commit(
    repo_path: Path,
    commit_ref: str,
    discard_uncommitted_changes: bool = False,
) -> Generator[None, None, None]:
    """
    Temporarily checkout a specific commit, then restore original state.

    Args:
        repo_path: Path to the git repository
        commit_ref: Commit hash, branch name, or tag to checkout
        discard_uncommitted_changes: If True, PERMANENTLY DISCARDS any uncommitted
            changes before checkout. If False (default), raises GitContextError
            if there are uncommitted changes. Use stashed_changes() instead to
            preserve changes.

    Yields:
        None (repo is at specified commit during context)

    Raises:
        GitContextError: If checkout fails or uncommitted changes exist

    Example:
        with checkout_commit(repo, 'abc123'):
            # Analyze code at this specific commit
            old_entities = extract_entities(repo)
        # Repo is back to original state
    """
    # Check for uncommitted changes
    if not discard_uncommitted_changes and _has_uncommitted_changes(repo_path):
        raise GitContextError(
            "Repository has uncommitted changes. "
            "Commit or stash changes first, or use discard_uncommitted_changes=True."
        )

    # Save current state (works for both branch and detached HEAD)
    original_ref = _get_head_ref(repo_path)

    try:
        # Checkout the requested commit
        checkout_args = ['checkout']
        if discard_uncommitted_changes:
            checkout_args.append('--force')
        checkout_args.append(commit_ref)

        try:
            run_git_command(checkout_args, repo_path)
        except GitCommandError as e:
            raise GitContextError(f"Failed to checkout {commit_ref}: {e}") from e

        yield

    finally:
        # Restore original state
        try:
            run_git_command(['checkout', original_ref], repo_path)
        except GitCommandError:
            # If restore fails, try harder with --force
            # This can happen if files were modified during the context
            try:
                run_git_command(['checkout', '--force', original_ref], repo_path)
            except GitCommandError as e:
                # Last resort: leave repo in current state but warn
                warnings.warn(
                    f"Failed to restore git state to {original_ref}: {e}. "
                    "Repository may be in unexpected state.",
                    RuntimeWarning,
                )


@contextmanager
def stashed_changes(repo_path: Path) -> Generator[bool, None, None]:
    """
    Temporarily stash uncommitted changes, then restore them.

    Stashes both tracked changes and untracked files. On exit, automatically
    pops the stash to restore changes.

    Args:
        repo_path: Path to the git repository

    Yields:
        True if changes were stashed, False if working directory was clean

    Raises:
        GitContextError: If stashing fails (e.g., no git repo, merge conflict)

    Example:
        with stashed_changes(repo) as had_changes:
            # Working directory is clean
            with checkout_commit(repo, 'abc123'):
                analyze()
        # Original uncommitted changes are restored
    """
    had_changes = _has_uncommitted_changes(repo_path)

    if had_changes:
        try:
            stash_msg = f'docwatch: temporary stash at {datetime.now().isoformat()}'
            run_git_command(
                ['stash', 'push', '--include-untracked', '-m', stash_msg],
                repo_path
            )
        except GitCommandError as e:
            raise GitContextError(f"Failed to stash changes: {e}") from e

    try:
        yield had_changes
    finally:
        if had_changes:
            try:
                run_git_command(['stash', 'pop'], repo_path)
            except GitCommandError as e:
                warnings.warn(
                    f"Failed to restore stashed changes: {e}. "
                    "Changes may still be in stash.",
                    RuntimeWarning,
                )
