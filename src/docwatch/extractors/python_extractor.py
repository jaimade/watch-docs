"""
Extract structured information from Python source code.
"""
import ast
import re


def extract_function_names(content):
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
    # Pattern breakdown:
    #   \b       - word boundary (ensures we match 'def' as a keyword)
    #   def      - literal 'def' keyword
    #   \s+      - one or more whitespace characters
    #   (\w+)    - capture group: one or more word characters (the function name)
    #   \s*      - zero or more whitespace
    #   \(       - literal opening parenthesis
    pattern = r'\bdef\s+(\w+)\s*\('
    return re.findall(pattern, content)


def extract_class_names(content):
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
    # Pattern breakdown:
    #   \b       - word boundary (prevents matching 'class' inside 'dataclass')
    #   class    - literal 'class' keyword
    #   \s+      - one or more whitespace
    #   (\w+)    - capture group: the class name
    #   [\s(:]   - followed by whitespace, '(' or ':' (handles all cases)
    pattern = r'\bclass\s+(\w+)[\s(:]'
    return re.findall(pattern, content)


def extract_docstrings(content):
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
    except SyntaxError:
        return {}

    docstrings = {}

    for node in ast.walk(tree):
        # Check for functions and classes
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            docstring = ast.get_docstring(node)

            if docstring:
                docstrings[name] = docstring

    return docstrings


def extract_imports(content):
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
    except SyntaxError:
        return []

    imports = []

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
    seen = set()
    unique = []
    for imp in imports:
        if imp not in seen:
            seen.add(imp)
            unique.append(imp)

    return unique
