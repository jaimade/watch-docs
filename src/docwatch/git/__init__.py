"""Git integration for detecting code changes."""

from .commands import (
    GitCommandError,
    GitParseError,
    Commit,
    ChangedFile,
    run_git_command,
    get_current_branch,
    get_recent_commits,
    get_commit,
    get_commits_since,
    get_commits_between,
    get_changed_files,
    get_file_diff,
    get_file_at_commit,
)
from .tracker import (
    ChangeType,
    AnalyzedChange,
    AnalyzedCommit,
    EntityChange,
    ChangeTracker,
)
from .impact import (
    ImpactType,
    DocumentationImpact,
    ImpactAnalyzer,
)
from .context import (
    GitContextError,
    cloned_repo,
    checkout_commit,
    stashed_changes,
)

__all__ = [
    # Exceptions
    'GitCommandError',
    'GitParseError',
    'GitContextError',
    # Low-level data classes
    'Commit',
    'ChangedFile',
    # High-level data classes
    'ChangeType',
    'AnalyzedChange',
    'AnalyzedCommit',
    'EntityChange',
    # Impact analysis
    'ImpactType',
    'DocumentationImpact',
    'ImpactAnalyzer',
    # Tracker
    'ChangeTracker',
    # Context managers
    'cloned_repo',
    'checkout_commit',
    'stashed_changes',
    # Functions
    'run_git_command',
    'get_current_branch',
    'get_recent_commits',
    'get_commit',
    'get_commits_since',
    'get_commits_between',
    'get_changed_files',
    'get_file_diff',
    'get_file_at_commit',
]
