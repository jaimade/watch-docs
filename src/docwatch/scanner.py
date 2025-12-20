"""
File scanner for categorizing code and documentation files
"""
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
