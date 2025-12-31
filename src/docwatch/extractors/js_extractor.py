"""
Extract structured information from JavaScript/TypeScript source code.
"""
from docwatch.extractors.patterns import (
    JS_FUNCTION_DECLARATION,
    JS_ARROW_FUNCTION,
    JS_FUNCTION_EXPRESSION,
    JS_CLASS_DEF,
    JS_ES6_IMPORT,
    JS_SIDE_EFFECT_IMPORT,
    JS_REQUIRE,
    JS_DYNAMIC_IMPORT,
    JS_EXPORT_DECLARATION,
    JS_EXPORT_BRACES,
)

__all__ = [
    "extract_function_names",
    "extract_class_names",
    "extract_imports",
    "extract_exports",
]


def extract_function_names(content: str) -> list[str]:
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

    # Traditional function declarations
    functions.extend(JS_FUNCTION_DECLARATION.findall(content))

    # Arrow functions
    functions.extend(JS_ARROW_FUNCTION.findall(content))

    # Function expressions
    functions.extend(JS_FUNCTION_EXPRESSION.findall(content))

    # Return unique, preserving order
    seen = set()
    unique = []
    for name in functions:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    return unique


def extract_class_names(content: str) -> list[str]:
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
    return JS_CLASS_DEF.findall(content)


def extract_imports(content: str) -> list[str]:
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

    # ES6 imports
    imports.extend(JS_ES6_IMPORT.findall(content))

    # Side-effect imports
    imports.extend(JS_SIDE_EFFECT_IMPORT.findall(content))

    # CommonJS require
    imports.extend(JS_REQUIRE.findall(content))

    # Dynamic imports
    imports.extend(JS_DYNAMIC_IMPORT.findall(content))

    # Return unique, preserving order
    seen = set()
    unique = []
    for name in imports:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    return unique


def extract_exports(content: str) -> list[str]:
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
    exports.extend(JS_EXPORT_DECLARATION.findall(content))

    # export { name, name2 }
    for match in JS_EXPORT_BRACES.findall(content):
        # Split by comma and clean up
        names = [n.strip().split(' ')[0] for n in match.split(',')]
        exports.extend(n for n in names if n and n.isidentifier())

    # Return unique, preserving order
    seen = set()
    unique = []
    for name in exports:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    return unique
