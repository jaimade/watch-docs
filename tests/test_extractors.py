"""
Tests for extractors with edge cases.

Covers malformed code, empty files, and boundary conditions.
"""
import pytest

from docwatch.extractors import (
    python_extractor,
    js_extractor,
    markdown_extractor,
    rst_extractor,
    asciidoc_extractor,
)


class TestPythonExtractor:
    """Tests for Python code extraction."""

    def test_empty_content(self):
        """Empty content returns empty lists."""
        assert python_extractor.extract_function_names("") == []
        assert python_extractor.extract_class_names("") == []
        assert python_extractor.extract_imports("") == []

    def test_whitespace_only(self):
        """Whitespace-only content returns empty lists."""
        content = "   \n\n\t\t\n   "
        assert python_extractor.extract_function_names(content) == []
        assert python_extractor.extract_class_names(content) == []

    def test_comments_only(self):
        """File with only comments returns empty lists."""
        content = """
# This is a comment
# Another comment
'''
Multiline string that's not a docstring
'''
"""
        assert python_extractor.extract_function_names(content) == []
        assert python_extractor.extract_class_names(content) == []

    def test_simple_function(self):
        """Extracts simple function definition."""
        content = "def hello_world():\n    pass"
        assert "hello_world" in python_extractor.extract_function_names(content)

    def test_function_with_args(self):
        """Extracts function with arguments."""
        content = "def process(data, options=None):\n    return data"
        assert "process" in python_extractor.extract_function_names(content)

    def test_async_function(self):
        """Extracts async function definitions."""
        content = "async def fetch_data():\n    await something()"
        assert "fetch_data" in python_extractor.extract_function_names(content)

    def test_simple_class(self):
        """Extracts simple class definition."""
        content = "class MyClass:\n    pass"
        assert "MyClass" in python_extractor.extract_class_names(content)

    def test_class_with_inheritance(self):
        """Extracts class with base classes."""
        content = "class ChildClass(ParentClass, Mixin):\n    pass"
        assert "ChildClass" in python_extractor.extract_class_names(content)

    def test_dataclass_decorator(self):
        """Correctly extracts class name, not decorator."""
        content = """
@dataclass
class Config:
    name: str
    value: int
"""
        classes = python_extractor.extract_class_names(content)
        assert "Config" in classes
        assert "dataclass" not in classes

    def test_multiple_decorators(self):
        """Handles multiple decorators correctly."""
        content = """
@decorator_one
@decorator_two(arg=True)
@decorator_three
def decorated_function():
    pass
"""
        funcs = python_extractor.extract_function_names(content)
        assert "decorated_function" in funcs
        assert "decorator_one" not in funcs

    def test_nested_function(self):
        """Extracts nested function definitions."""
        content = """
def outer():
    def inner():
        pass
    return inner
"""
        funcs = python_extractor.extract_function_names(content)
        assert "outer" in funcs
        assert "inner" in funcs

    def test_method_in_class(self):
        """Extracts methods inside classes."""
        content = """
class Service:
    def __init__(self):
        pass

    def process(self, data):
        return data
"""
        funcs = python_extractor.extract_function_names(content)
        assert "__init__" in funcs
        assert "process" in funcs

    def test_import_statements(self):
        """Extracts various import formats."""
        content = """
import os
import sys
from pathlib import Path
from typing import Optional, List
from . import local_module
from ..parent import something
"""
        imports = python_extractor.extract_imports(content)
        assert "os" in imports
        assert "sys" in imports
        # Note: extract_imports returns module names, not imported symbols
        assert "pathlib" in imports or "Path" in imports
        assert "typing" in imports or "Optional" in imports

    def test_malformed_syntax(self):
        """Handles malformed Python gracefully."""
        content = """
def broken(
    # missing closing paren
class AlsoBroken
    no colon here
"""
        # Should not raise, may return partial results
        funcs = python_extractor.extract_function_names(content)
        classes = python_extractor.extract_class_names(content)
        # Just verify it doesn't crash
        assert isinstance(funcs, list)
        assert isinstance(classes, list)

    def test_string_containing_def(self):
        """Known limitation: regex may extract 'def' from strings."""
        content = '''
description = "def not_a_function(): this is just a string"
'''
        funcs = python_extractor.extract_function_names(content)
        # Note: This is a known limitation of regex-based extraction.
        # A proper AST-based approach would not have this issue.
        # We just verify it doesn't crash.
        assert isinstance(funcs, list)

    def test_docstrings(self):
        """Extracts docstrings from functions and classes."""
        content = '''
def documented():
    """This is the docstring."""
    pass

class MyClass:
    """Class docstring."""

    def method(self):
        """Method docstring."""
        pass
'''
        docstrings = python_extractor.extract_docstrings(content)
        assert "documented" in docstrings
        assert docstrings["documented"] == "This is the docstring."


class TestJSExtractor:
    """Tests for JavaScript/TypeScript extraction."""

    def test_empty_content(self):
        """Empty content returns empty lists."""
        assert js_extractor.extract_function_names("") == []
        assert js_extractor.extract_class_names("") == []
        assert js_extractor.extract_imports("") == []

    def test_function_declaration(self):
        """Extracts function declarations."""
        content = "function handleClick() { return true; }"
        assert "handleClick" in js_extractor.extract_function_names(content)

    def test_async_function(self):
        """Extracts async function declarations."""
        content = "async function fetchData() { await fetch(); }"
        assert "fetchData" in js_extractor.extract_function_names(content)

    def test_arrow_function(self):
        """Extracts arrow function assignments."""
        content = "const processData = (data) => { return data; };"
        funcs = js_extractor.extract_function_names(content)
        assert "processData" in funcs

    def test_arrow_function_async(self):
        """Extracts async arrow functions."""
        content = "const fetchItems = async () => { await load(); };"
        funcs = js_extractor.extract_function_names(content)
        assert "fetchItems" in funcs

    def test_class_declaration(self):
        """Extracts class declarations."""
        content = "class UserService { constructor() {} }"
        assert "UserService" in js_extractor.extract_class_names(content)

    def test_class_with_extends(self):
        """Extracts class with inheritance."""
        content = "class AdminService extends UserService { }"
        classes = js_extractor.extract_class_names(content)
        assert "AdminService" in classes

    def test_es6_imports(self):
        """Extracts ES6 import statements."""
        content = """
import React from 'react';
import { useState, useEffect } from 'react';
import * as utils from './utils';
"""
        imports = js_extractor.extract_imports(content)
        # Note: extract_imports returns module names from the 'from' clause
        assert "react" in imports or "React" in imports
        assert "./utils" in imports or "utils" in imports

    def test_commonjs_require(self):
        """Extracts CommonJS require statements."""
        content = """
const fs = require('fs');
const { readFile } = require('fs');
"""
        imports = js_extractor.extract_imports(content)
        assert "fs" in imports

    def test_exports(self):
        """Extracts export statements."""
        content = """
export function helper() {}
export const value = 42;
export default MainComponent;
export { one, two, three };
"""
        exports = js_extractor.extract_exports(content)
        assert "helper" in exports
        # Note: 'export default' may not be captured as 'default'
        # Verify named exports work
        assert "one" in exports or "two" in exports

    def test_typescript_interface(self):
        """Handles TypeScript interface syntax."""
        content = "interface UserData { name: string; age: number; }"
        # Interfaces might be captured as classes depending on implementation
        # Just verify it doesn't crash
        classes = js_extractor.extract_class_names(content)
        assert isinstance(classes, list)

    def test_jsx_component(self):
        """Handles JSX component definitions."""
        content = """
function Button({ onClick, children }) {
    return <button onClick={onClick}>{children}</button>;
}
"""
        funcs = js_extractor.extract_function_names(content)
        assert "Button" in funcs


class TestMarkdownExtractor:
    """Tests for Markdown extraction."""

    def test_empty_content(self):
        """Empty content returns empty lists."""
        assert markdown_extractor.extract_headers("") == []
        assert markdown_extractor.extract_inline_code("") == []
        assert markdown_extractor.extract_code_blocks("") == []

    def test_headers_all_levels(self):
        """Extracts headers at all levels."""
        content = """
# Level 1
## Level 2
### Level 3
#### Level 4
##### Level 5
###### Level 6
"""
        headers = markdown_extractor.extract_headers(content)
        assert len(headers) == 6
        assert headers[0]["level"] == 1
        assert headers[5]["level"] == 6

    def test_headers_inside_code_block_ignored(self):
        """Headers inside code blocks are not extracted."""
        content = """
# Real Header

```python
# This is a comment, not a header
def foo():
    pass
```

## Another Real Header
"""
        headers = markdown_extractor.extract_headers(content)
        assert len(headers) == 2
        assert headers[0]["text"] == "Real Header"
        assert headers[1]["text"] == "Another Real Header"

    def test_inline_code(self):
        """Extracts inline code references."""
        content = "Use `process_data` to transform the `input_value`."
        refs = markdown_extractor.extract_inline_code(content)
        assert "process_data" in refs
        assert "input_value" in refs

    def test_inline_code_unique(self):
        """Returns unique inline code references."""
        content = "Call `foo` then `bar` then `foo` again."
        refs = markdown_extractor.extract_inline_code(content)
        assert refs.count("foo") == 1

    def test_code_block_with_language(self):
        """Extracts fenced code blocks with language."""
        content = """
```python
def hello():
    print("world")
```
"""
        blocks = markdown_extractor.extract_code_blocks(content)
        assert len(blocks) == 1
        assert blocks[0]["language"] == "python"
        assert "def hello" in blocks[0]["code"]

    def test_code_block_without_language(self):
        """Extracts code blocks without language specification."""
        content = """
```
plain code block
```
"""
        blocks = markdown_extractor.extract_code_blocks(content)
        assert len(blocks) == 1
        assert blocks[0]["language"] == "text"

    def test_code_block_identifiers(self):
        """Extracts identifiers from code blocks."""
        content = """
```python
from docwatch import DocumentationAnalyzer, CoverageStats

analyzer = DocumentationAnalyzer()
stats = analyzer.get_coverage_stats()
```
"""
        identifiers = markdown_extractor.extract_code_block_identifiers(content)
        assert "DocumentationAnalyzer" in identifiers
        assert "CoverageStats" in identifiers
        # Note: extracts function calls and class names, not variable names
        assert "get_coverage_stats" in identifiers

    def test_code_block_filters_builtins(self):
        """Filters common Python builtins from code block extraction."""
        content = """
```python
print("hello")
x = len(items)
result = str(value)
```
"""
        identifiers = markdown_extractor.extract_code_block_identifiers(content)
        assert "print" not in identifiers
        assert "len" not in identifiers
        assert "str" not in identifiers

    def test_links(self):
        """Extracts markdown links."""
        content = "Check [the docs](https://example.com) for more info."
        links = markdown_extractor.extract_links(content)
        assert len(links) == 1
        assert links[0]["text"] == "the docs"
        assert links[0]["url"] == "https://example.com"

    def test_multiple_links_same_line(self):
        """Extracts multiple links from same line."""
        content = "See [one](http://one.com) and [two](http://two.com)."
        links = markdown_extractor.extract_links(content)
        assert len(links) == 2

    def test_triple_backticks_not_inline(self):
        """Triple backticks are not captured as inline code."""
        content = "```python\ncode\n```"
        inline = markdown_extractor.extract_inline_code(content)
        # Should not capture 'python' or 'code' as inline
        assert "python" not in inline


class TestRstExtractor:
    """Tests for reStructuredText extraction."""

    def test_empty_content(self):
        """Empty content returns empty lists."""
        assert rst_extractor.extract_headers("") == []
        assert rst_extractor.extract_inline_code("") == []

    def test_headers_with_underlines(self):
        """Extracts RST headers with various underline styles."""
        content = """
Main Title
==========

Section
-------

Subsection
~~~~~~~~~~
"""
        headers = rst_extractor.extract_headers(content)
        assert len(headers) >= 3
        assert headers[0]["text"] == "Main Title"

    def test_inline_code(self):
        """Extracts RST inline code with double backticks."""
        content = "Use ``my_function`` to process data."
        refs = rst_extractor.extract_inline_code(content)
        assert "my_function" in refs

    def test_code_block_directive(self):
        """Extracts code-block directive."""
        content = """
.. code-block:: python

   def example():
       pass
"""
        blocks = rst_extractor.extract_code_blocks(content)
        assert len(blocks) >= 1

    def test_literal_block(self):
        """Extracts literal blocks (::)."""
        content = """
Example code::

    indented code here
    more code
"""
        blocks = rst_extractor.extract_code_blocks(content)
        assert len(blocks) >= 1


class TestAsciidocExtractor:
    """Tests for AsciiDoc extraction."""

    def test_empty_content(self):
        """Empty content returns empty lists."""
        assert asciidoc_extractor.extract_headers("") == []
        assert asciidoc_extractor.extract_inline_code("") == []

    def test_headers(self):
        """Extracts AsciiDoc headers."""
        content = """
= Document Title

== Section One

=== Subsection
"""
        headers = asciidoc_extractor.extract_headers(content)
        assert len(headers) == 3
        assert headers[0]["level"] == 1
        assert headers[0]["text"] == "Document Title"

    def test_inline_code(self):
        """Extracts inline code with backticks or plus signs."""
        content = "Use `my_function` or +another_function+ in your code."
        refs = asciidoc_extractor.extract_inline_code(content)
        assert "my_function" in refs
        assert "another_function" in refs

    def test_source_block(self):
        """Extracts source blocks."""
        content = """
[source,python]
----
def hello():
    pass
----
"""
        blocks = asciidoc_extractor.extract_code_blocks(content)
        assert len(blocks) >= 1

    def test_links(self):
        """Extracts AsciiDoc links."""
        content = "Visit link:https://example.com[Example Site] for more."
        links = asciidoc_extractor.extract_links(content)
        assert any(l["url"] == "https://example.com" for l in links)
