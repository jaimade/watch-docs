"""
File scanner for categorizing code and documentation files.

Provides utilities for:
- Recursively scanning directories for files
- Categorizing files as code or documentation
- Gathering file statistics

Performance features:
- Batched iteration for backpressure with large directories
- Progress callbacks for monitoring long scans
"""
from collections import Counter
from pathlib import Path
from typing import Callable, Iterator, Optional

from rich.console import Console

from docwatch.constants import (
    DEFAULT_IGNORE_DIRS,
    CODE_EXTENSIONS,
    DOC_EXTENSIONS,
)

console = Console(stderr=True)

# Default batch size for batched file iteration
DEFAULT_BATCH_SIZE = 1000


def should_ignore(path: Path, ignore_dirs: frozenset[str]) -> bool:
    """
    Check if a path should be ignored based on directory names.

    Args:
        path: Path to check
        ignore_dirs: Set of directory names to ignore

    Returns:
        True if any parent directory is in ignore_dirs
    """
    for part in path.parts:
        if part in ignore_dirs:
            return True
        # Also check for .egg-info suffix
        if part.endswith('.egg-info'):
            return True
    return False


def get_all_files(
    directory: Path | str,
    ignore_dirs: Optional[frozenset[str]] = None,
) -> Iterator[Path]:
    """
    Get all files recursively from a directory.

    Args:
        directory: Path to directory (string or Path object)
        ignore_dirs: Set of directory names to ignore (default: DEFAULT_IGNORE_DIRS)

    Yields:
        Path objects pointing to files

    Raises:
        TypeError: If directory is not a string or Path object (raised by Path())
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path points to a file, not a directory
    """
    if ignore_dirs is None:
        ignore_dirs = DEFAULT_IGNORE_DIRS

    dir_path = Path(directory)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory does not exist: {dir_path}")

    if not dir_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {dir_path}")

    for item in dir_path.rglob('*'):
        try:
            # Skip ignored directories
            if should_ignore(item, ignore_dirs):
                continue

            if item.is_file():
                yield item
        except PermissionError:
            console.print(f"[yellow]Warning:[/] Permission denied for {item}", style="dim")
            continue


def get_all_files_batched(
    directory: Path | str,
    batch_size: int = DEFAULT_BATCH_SIZE,
    ignore_dirs: Optional[frozenset[str]] = None,
    on_batch: Optional[Callable[[list[Path], int], None]] = None,
) -> Iterator[list[Path]]:
    """
    Get files in batches for backpressure with large directories.

    This is useful when scanning 100K+ files where you want to:
    - Process files in manageable chunks
    - Report progress to users
    - Allow garbage collection between batches

    Args:
        directory: Path to directory (string or Path object)
        batch_size: Number of files per batch (default: 1000)
        ignore_dirs: Set of directory names to ignore
        on_batch: Optional callback called after each batch with
                  (batch, total_so_far). Useful for progress reporting.

    Yields:
        Lists of Path objects, each up to batch_size length

    Example:
        for batch in get_all_files_batched("/large/project", batch_size=500):
            process_files(batch)
            # GC can reclaim previous batch memory here

        # With progress callback:
        def show_progress(batch, total):
            print(f"Scanned {total} files...")

        for batch in get_all_files_batched("/project", on_batch=show_progress):
            process_files(batch)
    """
    batch: list[Path] = []
    total_count = 0

    for filepath in get_all_files(directory, ignore_dirs=ignore_dirs):
        batch.append(filepath)
        total_count += 1

        if len(batch) >= batch_size:
            if on_batch:
                on_batch(batch, total_count)
            yield batch
            batch = []

    # Yield any remaining files
    if batch:
        if on_batch:
            on_batch(batch, total_count)
        yield batch


def scan_with_progress(
    directory: Path | str,
    ignore_dirs: Optional[frozenset[str]] = None,
    report_every: int = 1000,
) -> Iterator[Path]:
    """
    Scan files with automatic progress reporting to stderr.

    Prints progress every `report_every` files, useful for long scans.

    Args:
        directory: Path to directory
        ignore_dirs: Set of directory names to ignore
        report_every: Print progress every N files (default: 1000)

    Yields:
        Path objects pointing to files
    """
    count = 0
    for filepath in get_all_files(directory, ignore_dirs=ignore_dirs):
        count += 1
        if count % report_every == 0:
            console.print(f"[dim]Scanned {count:,} files...[/]", highlight=False)
        yield filepath

    if count >= report_every:
        console.print(f"[dim]Scan complete: {count:,} files[/]", highlight=False)


def is_code_file(filepath: Path | str) -> bool:
    """
    Check if a file is a code file based on its extension.

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        True if file has a code extension, False otherwise
    """
    path = Path(filepath)
    return path.suffix.lower() in CODE_EXTENSIONS


def is_doc_file(filepath: Path | str) -> bool:
    """
    Check if a file is a documentation file based on its extension.

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        True if file has a documentation extension, False otherwise
    """
    path = Path(filepath)
    return path.suffix.lower() in DOC_EXTENSIONS


def categorize_files(
    directory: Path | str,
    ignore_dirs: Optional[frozenset[str]] = None,
) -> dict[str, list[Path]]:
    """
    Scan a directory and categorize files as code or documentation.

    Args:
        directory: Path to directory (string or Path object)
        ignore_dirs: Set of directory names to ignore (default: DEFAULT_IGNORE_DIRS)

    Returns:
        dict: {'code': [Path, ...], 'docs': [Path, ...]}

    Raises:
        TypeError: If directory is not a string or Path object
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path points to a file, not a directory
    """
    all_files = get_all_files(directory, ignore_dirs=ignore_dirs)

    code_files = []
    doc_files = []

    for filepath in all_files:
        if is_code_file(filepath):
            code_files.append(filepath)
        elif is_doc_file(filepath):
            doc_files.append(filepath)

    return {'code': code_files, 'docs': doc_files}


def get_directory_stats(
    directory: Path | str,
    top_n: int = 10,
    ignore_dirs: Optional[frozenset[str]] = None,
) -> dict:
    """
    Get comprehensive statistics about files in a directory.

    Args:
        directory: Path to directory (string or Path object)
        top_n: Number of largest files to include (default 10)
        ignore_dirs: Set of directory names to ignore (default: DEFAULT_IGNORE_DIRS)

    Returns:
        Dictionary with keys:
        - total_files: int
        - by_category: {'code': int, 'docs': int, 'other': int}
        - by_extension: {'.py': int, '.js': int, ...}
        - largest_files: [{'path': Path, 'size': int}, ...]

    Raises:
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path points to a file, not a directory
    """
    # Count by category
    code_count = 0
    docs_count = 0
    other_count = 0
    total_count = 0

    # Track extensions and file sizes
    extensions = []
    file_sizes = []

    for filepath in get_all_files(directory, ignore_dirs=ignore_dirs):
        total_count += 1

        # Categorize
        if is_code_file(filepath):
            code_count += 1
        elif is_doc_file(filepath):
            docs_count += 1
        else:
            other_count += 1

        # Track extension
        ext = filepath.suffix.lower()
        if ext:  # Only count files with extensions
            extensions.append(ext)

        # Get file size (handle permission errors)
        try:
            size = filepath.stat().st_size
            file_sizes.append({'path': filepath, 'size': size})
        except (PermissionError, OSError):
            continue

    # Sort by size descending and take top N
    largest_files = sorted(file_sizes, key=lambda x: x['size'], reverse=True)[:top_n]

    return {
        'total_files': total_count,
        'by_category': {
            'code': code_count,
            'docs': docs_count,
            'other': other_count
        },
        'by_extension': dict(Counter(extensions).most_common()),
        'largest_files': largest_files
    }
