"""
Extract structured information from Python source code.
"""
import ast
import logging

from docwatch.extractors.patterns import PYTHON_FUNCTION_DEF, PYTHON_CLASS_DEF

logger = logging.getLogger(__name__)

__all__ = [
    "extract_function_names",
    "extract_class_names",
    "extract_docstrings",
    "extract_imports",
]


def extract_function_names(content: str) -> list[str]:
    """
    Extract all function names from Python code.

    Args:
        content: Python source code as a string

    Returns:
        list: Function names found in the code

    Example:
        >>> extract_function_names("def hello(): pass")
        ['hello']
    """
    return PYTHON_FUNCTION_DEF.findall(content)


def extract_class_names(content: str) -> list[str]:
    """
    Extract all class names from Python code.

    Args:
        content: Python source code as a string

    Returns:
        list: Class names found in the code

    Example:
        >>> extract_class_names("class MyClass: pass")
        ['MyClass']
        >>> extract_class_names("class Child(Parent): pass")
        ['Child']
    """
    return PYTHON_CLASS_DEF.findall(content)


def extract_docstrings(content: str) -> dict[str, str]:
    """
    Extract function and class docstrings from Python code.

    Uses Python's ast module to properly parse the code,
    handling all docstring formats (single-line, multi-line, single/double quotes).

    Args:
        content: Python source code as a string

    Returns:
        dict: {'function_or_class_name': 'docstring content', ...}
              Only includes items that have docstrings.
              Returns empty dict if code can't be parsed.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("Failed to parse Python source for docstrings: %s at line %s", e.msg, e.lineno)
        return {}

    docstrings: dict[str, str] = {}

    for node in ast.walk(tree):
        # Check for functions and classes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            docstring = ast.get_docstring(node)

            if docstring:
                docstrings[name] = docstring

    return docstrings


def extract_imports(content: str) -> list[str]:
    """
    Extract all import statements from Python code.

    Args:
        content: Python source code as a string

    Returns:
        list: Module names that are imported

    Example:
        >>> extract_imports("import os\\nfrom pathlib import Path")
        ['os', 'pathlib']
    """
    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        logger.debug("Failed to parse Python source for imports: %s at line %s", e.msg, e.lineno)
        return []

    imports: list[str] = []

    for node in ast.walk(tree):
        # import x, y, z
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name.split('.')[0])  # Get top-level module

        # from x import y
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module.split('.')[0])

    # Return unique imports, preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for imp in imports:
        if imp not in seen:
            seen.add(imp)
            unique.append(imp)

    return unique
