"""
Extract structured information from JavaScript/TypeScript source code.
"""
import re


def extract_function_names(content):
    """
    Extract function names from JavaScript/TypeScript code.

    Matches:
    - function name() {}
    - async function name() {}
    - const name = function() {}
    - const name = () => {}
    - const name = async () => {}

    Args:
        content: JS/TS source code as a string

    Returns:
        list: Function names found in the code
    """
    functions = []

    # Traditional function declarations: function name() or async function name()
    # \b ensures we don't match inside other words
    pattern1 = r'\b(?:async\s+)?function\s+(\w+)\s*\('
    functions.extend(re.findall(pattern1, content))

    # Arrow functions and function expressions assigned to const/let/var
    # const name = () => {} or const name = function() {}
    pattern2 = r'\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[\w]+)\s*=>'
    functions.extend(re.findall(pattern2, content))

    # Function expressions: const name = function() {}
    pattern3 = r'\b(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?function\s*\('
    functions.extend(re.findall(pattern3, content))

    # Return unique, preserving order
    seen = set()
    unique = []
    for name in functions:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    return unique


def extract_class_names(content):
    """
    Extract class names from JavaScript/TypeScript code.

    Matches:
    - class Name {}
    - class Name extends Parent {}
    - export class Name {}

    Args:
        content: JS/TS source code as a string

    Returns:
        list: Class names found in the code
    """
    # Pattern: optional export, then class keyword, then name
    # \b prevents matching inside words
    # [\w.]+ allows for Parent.Child style extends (e.g., React.Component)
    pattern = r'\bclass\s+(\w+)(?:\s+extends\s+[\w.]+)?(?:\s+implements\s+[\w.,\s]+)?\s*\{'
    return re.findall(pattern, content)


def extract_imports(content):
    """
    Extract import statements from JavaScript/TypeScript code.

    Matches:
    - import x from 'module'
    - import { x } from 'module'
    - import * as x from 'module'
    - const x = require('module')

    Args:
        content: JS/TS source code as a string

    Returns:
        list: Module names that are imported
    """
    imports = []

    # ES6 imports: import ... from 'module' or "module"
    pattern1 = r'\bimport\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]'
    imports.extend(re.findall(pattern1, content))

    # Side-effect imports: import 'module'
    pattern2 = r'\bimport\s+[\'"]([^\'"]+)[\'"]'
    imports.extend(re.findall(pattern2, content))

    # CommonJS require: require('module')
    pattern3 = r'\brequire\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
    imports.extend(re.findall(pattern3, content))

    # Dynamic imports: import('module')
    pattern4 = r'\bimport\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)'
    imports.extend(re.findall(pattern4, content))

    # Return unique, preserving order
    seen = set()
    unique = []
    for name in imports:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    return unique


def extract_exports(content):
    """
    Extract exported names from JavaScript/TypeScript code.

    Matches:
    - export function name
    - export class name
    - export const name
    - export default name
    - export { name }

    Args:
        content: JS/TS source code as a string

    Returns:
        list: Names that are exported
    """
    exports = []

    # export function/class/const name
    pattern1 = r'\bexport\s+(?:default\s+)?(?:async\s+)?(?:function|class|const|let|var)\s+(\w+)'
    exports.extend(re.findall(pattern1, content))

    # export { name, name2 }
    pattern2 = r'\bexport\s*\{([^}]+)\}'
    for match in re.findall(pattern2, content):
        # Split by comma and clean up
        names = [n.strip().split(' ')[0] for n in match.split(',')]
        exports.extend(n for n in names if n and n.isidentifier())

    # export default (for anonymous)
    # We skip these as they don't have names

    # Return unique, preserving order
    seen = set()
    unique = []
    for name in exports:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    return unique
