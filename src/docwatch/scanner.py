"""
File scanner for categorizing code and documentation files
"""
from collections import Counter
from pathlib import Path


# Code file extensions
CODE_EXTENSIONS = {
    '.py', '.js', '.ts', '.tsx', '.jsx',
    '.php', '.rb', '.java', '.c', '.cpp',
    '.h', '.hpp', '.cs', '.go', '.rs',
    '.swift', '.kt', '.scala', '.sh',
    '.bash', '.zsh', '.fish', '.sql',
    '.html', '.css', '.scss', '.sass',
    '.vue', '.svelte', '.lua', '.r',
    '.m', '.mm', '.pl', '.pm'
}

# Documentation file extensions
DOC_EXTENSIONS = {
    '.md', '.markdown',
    '.rst',
    '.txt',
    '.adoc', '.asciidoc',
    '.org',
    '.tex', '.latex'
}


def get_all_files(directory):
    """
    Get all files recursively from a directory.

    Args:
        directory: Path to directory (string or Path object)

    Returns:
        List of Path objects pointing to files

    Raises:
        TypeError: If directory is not a string or Path object (raised by Path())
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path points to a file, not a directory
    """
    # Convert to Path object (automatically validates type)
    dir_path = Path(directory)

    if not dir_path.exists():
        raise FileNotFoundError(f"Directory does not exist: {dir_path}")

    if not dir_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {dir_path}")

    # Collect files, handling permission errors
    files = []
    for item in dir_path.rglob('*'):
        try:
            if item.is_file():
                files.append(item)
        except PermissionError:
            # Skip files/dirs we can't access
            print(f"Warning: Permission denied for {item}")
            continue

    return files


def is_code_file(filepath):
    """
    Check if a file is a code file based on its extension.

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        bool: True if file has a code extension, False otherwise
    """
    path = Path(filepath)
    return path.suffix.lower() in CODE_EXTENSIONS


def is_doc_file(filepath):
    """
    Check if a file is a documentation file based on its extension.

    Args:
        filepath: Path to file (string or Path object)

    Returns:
        bool: True if file has a documentation extension, False otherwise
    """
    path = Path(filepath)
    return path.suffix.lower() in DOC_EXTENSIONS


def categorize_files(directory):
    """
    Scan a directory and categorize files as code or documentation.

    Args:
        directory: Path to directory (string or Path object)

    Returns:
        dict: {'code': [Path, ...], 'docs': [Path, ...]}

    Raises:
        TypeError: If directory is not a string or Path object
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path points to a file, not a directory
    """
    all_files = get_all_files(directory)

    code_files = []
    doc_files = []

    for filepath in all_files:
        if is_code_file(filepath):
            code_files.append(filepath)
        elif is_doc_file(filepath):
            doc_files.append(filepath)

    return {'code': code_files, 'docs': doc_files}


def get_directory_stats(directory, top_n=10):
    """
    Get comprehensive statistics about files in a directory.

    Args:
        directory: Path to directory (string or Path object)
        top_n: Number of largest files to include (default 10)

    Returns:
        dict: {
            'total_files': int,
            'by_category': {'code': int, 'docs': int, 'other': int},
            'by_extension': {'.py': int, '.js': int, ...},
            'largest_files': [{'path': Path, 'size': int}, ...]
        }

    Raises:
        TypeError: If directory is not a string or Path object
        FileNotFoundError: If directory doesn't exist
        NotADirectoryError: If path points to a file, not a directory
    """
    all_files = get_all_files(directory)

    # Count by category
    code_count = 0
    docs_count = 0
    other_count = 0

    # Track extensions and file sizes
    extensions = []
    file_sizes = []

    for filepath in all_files:
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
        'total_files': len(all_files),
        'by_category': {
            'code': code_count,
            'docs': docs_count,
            'other': other_count
        },
        'by_extension': dict(Counter(extensions).most_common()),
        'largest_files': largest_files
    }
