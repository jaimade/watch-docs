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
    #   def      - literal 'def' keyword
    #   \s+      - one or more whitespace characters
    #   (\w+)    - capture group: one or more word characters (the function name)
    #   \s*      - zero or more whitespace
    #   \(       - literal opening parenthesis
    pattern = r'def\s+(\w+)\s*\('
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
    #   class    - literal 'class' keyword
    #   \s+      - one or more whitespace
    #   (\w+)    - capture group: the class name
    #   [\s(:]   - followed by whitespace, '(' or ':' (handles all cases)
    pattern = r'class\s+(\w+)[\s(:]'
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
