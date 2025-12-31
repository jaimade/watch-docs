"""
Tests for edge cases in extraction and file handling.

Covers:
- Jupyter notebook extraction
- Encoding edge cases (BOM, Latin-1, PEP 263)
- Large file performance
- Malformed input files
- Syntax errors in source files
"""
import json
import tempfile
import time
from pathlib import Path

import pytest

from docwatch.extractors.notebook_extractor import (
    NotebookExtractor,
    extract_from_notebook,
)
from docwatch.extractors.python_ast import (
    PythonASTExtractor,
    extract_from_file,
    extract_from_source,
    _detect_encoding,
)
from docwatch.extractor import extract_code_file
from docwatch.readers import read_file_safe


class TestNotebookExtractor:
    """Tests for Jupyter notebook extraction."""

    def test_basic_notebook(self, tmp_path):
        """Extract entities from a simple notebook."""
        notebook = {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {},
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["def hello():\n", "    return 'world'\n"],
                    "outputs": [],
                },
            ],
        }
        nb_path = tmp_path / "test.ipynb"
        nb_path.write_text(json.dumps(notebook))

        entities, imports = extract_from_notebook(nb_path)

        assert len(entities) == 1
        assert entities[0].name == "hello"

    def test_multiple_cells(self, tmp_path):
        """Extract entities from multiple code cells."""
        notebook = {
            "nbformat": 4,
            "cells": [
                {"cell_type": "code", "source": "def func1(): pass", "outputs": []},
                {"cell_type": "markdown", "source": "# Header"},
                {"cell_type": "code", "source": "def func2(): pass", "outputs": []},
                {"cell_type": "code", "source": "class MyClass: pass", "outputs": []},
            ],
        }
        nb_path = tmp_path / "multi.ipynb"
        nb_path.write_text(json.dumps(notebook))

        entities, imports = extract_from_notebook(nb_path)

        names = {e.name for e in entities}
        assert names == {"func1", "func2", "MyClass"}

    def test_empty_notebook(self, tmp_path):
        """Handle notebook with no cells."""
        notebook = {"nbformat": 4, "cells": []}
        nb_path = tmp_path / "empty.ipynb"
        nb_path.write_text(json.dumps(notebook))

        entities, imports = extract_from_notebook(nb_path)

        assert entities == []
        assert imports == []

    def test_only_markdown_cells(self, tmp_path):
        """Handle notebook with only markdown cells."""
        notebook = {
            "nbformat": 4,
            "cells": [
                {"cell_type": "markdown", "source": "# Title"},
                {"cell_type": "markdown", "source": "Some text"},
            ],
        }
        nb_path = tmp_path / "markdown_only.ipynb"
        nb_path.write_text(json.dumps(notebook))

        entities, imports = extract_from_notebook(nb_path)

        assert entities == []

    def test_malformed_json(self, tmp_path):
        """Handle invalid JSON gracefully."""
        nb_path = tmp_path / "bad.ipynb"
        nb_path.write_text("not valid json {{{")

        entities, imports = extract_from_notebook(nb_path)

        assert entities == []
        assert imports == []

    def test_missing_cells_key(self, tmp_path):
        """Handle notebook without cells key."""
        notebook = {"nbformat": 4}
        nb_path = tmp_path / "no_cells.ipynb"
        nb_path.write_text(json.dumps(notebook))

        entities, imports = extract_from_notebook(nb_path)

        assert entities == []

    def test_syntax_error_in_cell(self, tmp_path):
        """Handle syntax errors in code cells gracefully."""
        notebook = {
            "nbformat": 4,
            "cells": [
                {"cell_type": "code", "source": "def valid(): pass", "outputs": []},
                {"cell_type": "code", "source": "def broken(", "outputs": []},
                {"cell_type": "code", "source": "def also_valid(): pass", "outputs": []},
            ],
        }
        nb_path = tmp_path / "syntax_error.ipynb"
        nb_path.write_text(json.dumps(notebook))

        entities, imports = extract_from_notebook(nb_path)

        # Should extract from valid cells, skip broken one
        names = {e.name for e in entities}
        assert "valid" in names
        assert "also_valid" in names

    def test_imports_extraction(self, tmp_path):
        """Extract imports from notebook cells."""
        notebook = {
            "nbformat": 4,
            "cells": [
                {
                    "cell_type": "code",
                    "source": "import pandas as pd\nimport numpy as np",
                    "outputs": [],
                },
                {
                    "cell_type": "code",
                    "source": "from pathlib import Path",
                    "outputs": [],
                },
            ],
        }
        nb_path = tmp_path / "imports.ipynb"
        nb_path.write_text(json.dumps(notebook))

        entities, imports = extract_from_notebook(nb_path)

        assert "pandas" in imports
        assert "numpy" in imports
        assert "pathlib" in imports

    def test_via_extract_code_file(self, tmp_path):
        """Test notebook extraction via main extract_code_file function."""
        notebook = {
            "nbformat": 4,
            "cells": [
                {"cell_type": "code", "source": "def notebook_func(): pass", "outputs": []},
            ],
        }
        nb_path = tmp_path / "via_main.ipynb"
        nb_path.write_text(json.dumps(notebook))

        code_file = extract_code_file(nb_path)

        assert code_file is not None
        assert len(code_file.entities) == 1
        assert code_file.entities[0].name == "notebook_func"


class TestEncodingEdgeCases:
    """Tests for file encoding handling."""

    def test_utf8_default(self, tmp_path):
        """UTF-8 files work by default."""
        py_file = tmp_path / "utf8.py"
        py_file.write_text("def hello(): pass", encoding="utf-8")

        entities, imports = extract_from_file(py_file)

        assert len(entities) == 1
        assert entities[0].name == "hello"

    def test_utf8_with_emoji(self, tmp_path):
        """UTF-8 with emoji in docstrings."""
        py_file = tmp_path / "emoji.py"
        py_file.write_text(
            'def greet():\n    """Say hello 👋"""\n    return "🌍"',
            encoding="utf-8",
        )

        entities, imports = extract_from_file(py_file)

        assert len(entities) == 1
        assert "👋" in entities[0].docstring

    def test_utf8_bom(self, tmp_path):
        """UTF-8 with BOM (Byte Order Mark)."""
        py_file = tmp_path / "bom.py"
        py_file.write_text("def with_bom(): pass", encoding="utf-8-sig")

        detected = _detect_encoding(py_file)
        assert detected == "utf-8-sig"

        entities, imports = extract_from_file(py_file)
        assert len(entities) == 1

    def test_latin1_with_pep263(self, tmp_path):
        """Latin-1 file with PEP 263 coding declaration."""
        py_file = tmp_path / "latin1.py"
        content = b"# -*- coding: latin-1 -*-\ndef caf\xe9(): pass\n"
        py_file.write_bytes(content)

        detected = _detect_encoding(py_file)
        assert detected == "latin-1"

        entities, imports = extract_from_file(py_file)
        assert len(entities) == 1
        assert entities[0].name == "café"

    def test_cp1252_windows(self, tmp_path):
        """Windows CP1252 encoding with declaration."""
        py_file = tmp_path / "windows.py"
        content = b"# coding: cp1252\ndef func(): pass\n"
        py_file.write_bytes(content)

        detected = _detect_encoding(py_file)
        assert detected == "cp1252"

    def test_encoding_fallback(self, tmp_path):
        """Fall back to latin-1 for unknown encodings."""
        py_file = tmp_path / "unknown.py"
        # Write some non-UTF-8 bytes without a declaration
        content = b"def func(): x = 'caf\xe9'\n"
        py_file.write_bytes(content)

        # Should not crash, falls back to latin-1
        entities, imports = extract_from_file(py_file)
        assert len(entities) == 1

    def test_binary_file_handling(self, tmp_path):
        """Handle binary files gracefully."""
        bin_file = tmp_path / "binary.py"
        bin_file.write_bytes(b"\x00\x01\x02\x03def func(): pass")

        entities, imports = extract_from_file(bin_file)

        # Should not crash, may return empty or partial results
        assert isinstance(entities, list)

    def test_read_file_safe_encoding(self, tmp_path):
        """read_file_safe handles encoding fallback."""
        latin_file = tmp_path / "latin.txt"
        latin_file.write_bytes(b"caf\xe9")

        content = read_file_safe(latin_file)

        assert content is not None
        assert "caf" in content


class TestLargeFilePerformance:
    """Performance tests for large files."""

    def test_large_file_extraction(self, tmp_path):
        """Extract from a file with many functions."""
        # Generate a file with 1000 functions
        lines = ["# Large file"]
        for i in range(1000):
            lines.append(f"def function_{i}(): pass")

        py_file = tmp_path / "large.py"
        py_file.write_text("\n".join(lines))

        start = time.time()
        entities, imports = extract_from_file(py_file)
        elapsed = time.time() - start

        assert len(entities) == 1000
        assert elapsed < 2.0, f"Extraction took {elapsed:.2f}s, expected < 2s"

    def test_deeply_nested_code(self, tmp_path):
        """Handle deeply nested classes."""
        lines = ["class Outer:"]
        for i in range(20):
            indent = "    " * (i + 1)
            lines.append(f"{indent}class Nested{i}:")
            lines.append(f"{indent}    def method_{i}(self): pass")

        py_file = tmp_path / "nested.py"
        py_file.write_text("\n".join(lines))

        start = time.time()
        entities, imports = extract_from_file(py_file)
        elapsed = time.time() - start

        # Should find Outer + 20 nested classes + 20 methods = 41 entities
        assert len(entities) >= 21
        assert elapsed < 1.0

    def test_large_file_memory_generator(self):
        """Generator-based extraction doesn't accumulate memory."""
        # Generate source with many entities
        lines = ["# Memory test"]
        for i in range(500):
            lines.append(f"def func_{i}(): pass")
            lines.append(f"class Class_{i}: pass")

        source = "\n".join(lines)

        from docwatch.extractors.python_ast import iter_entities

        # Using generator - should be able to iterate without holding all in memory
        count = 0
        for entity in iter_entities(source, Path("test.py")):
            count += 1
            if count >= 100:
                break  # Early termination

        # We should be able to stop early
        assert count == 100


class TestMalformedInput:
    """Tests for handling malformed/invalid input."""

    def test_syntax_error_empty_result(self):
        """Syntax errors return empty results."""
        broken_code = "def broken(\n"

        entities, imports = extract_from_source(broken_code, Path("broken.py"))

        assert entities == []
        assert imports == []

    def test_incomplete_class(self):
        """Incomplete class definition."""
        code = "class Incomplete"

        entities, imports = extract_from_source(code, Path("test.py"))

        assert entities == []

    def test_indentation_error(self):
        """Indentation errors are handled."""
        code = "def func():\npass"  # Missing indent

        entities, imports = extract_from_source(code, Path("test.py"))

        assert entities == []

    def test_unclosed_string(self):
        """Unclosed string literal."""
        code = 'def func():\n    x = "unclosed'

        entities, imports = extract_from_source(code, Path("test.py"))

        assert entities == []

    def test_mixed_valid_invalid(self):
        """Only valid code before error is extracted."""
        # Note: Python's AST parser fails on the whole file, not just the error
        code = """
def valid1(): pass

def broken(

def valid2(): pass
"""
        entities, imports = extract_from_source(code, Path("test.py"))

        # AST parsing fails for entire file with syntax error
        assert entities == []

    def test_empty_file(self):
        """Empty files return empty results."""
        entities, imports = extract_from_source("", Path("empty.py"))

        assert entities == []
        assert imports == []

    def test_whitespace_only(self):
        """Whitespace-only files return empty results."""
        entities, imports = extract_from_source("   \n\n\t\t\n", Path("ws.py"))

        assert entities == []

    def test_comments_only(self):
        """Files with only comments return empty results."""
        code = """
# This is a comment
# Another comment
# No actual code
"""
        entities, imports = extract_from_source(code, Path("comments.py"))

        assert entities == []

    def test_nonexistent_file(self, tmp_path):
        """Nonexistent files return empty results."""
        fake_path = tmp_path / "does_not_exist.py"

        entities, imports = extract_from_file(fake_path)

        assert entities == []
        assert imports == []

    def test_directory_instead_of_file(self, tmp_path):
        """Directories return empty results."""
        entities, imports = extract_from_file(tmp_path)

        assert entities == []
        assert imports == []


class TestReDoSResistance:
    """Tests for regex denial-of-service resistance."""

    def test_markdown_missing_fence(self):
        """Markdown pattern handles missing closing fence."""
        from docwatch.extractors.patterns import MARKDOWN_FENCED_CODE_BLOCK

        # Malicious input: opening fence with no closing fence
        malicious = "```python\n" + "x = 1\n" * 10000

        start = time.time()
        matches = MARKDOWN_FENCED_CODE_BLOCK.findall(malicious)
        elapsed = time.time() - start

        assert matches == []
        assert elapsed < 0.5, f"Regex took {elapsed:.2f}s, potential ReDoS"

    def test_markdown_many_backticks(self):
        """Pattern handles many backtick sequences."""
        from docwatch.extractors.patterns import MARKDOWN_FENCED_CODE_BLOCK

        # Many potential fence starts
        content = ("```\n" * 100) + "```"

        start = time.time()
        matches = MARKDOWN_FENCED_CODE_BLOCK.findall(content)
        elapsed = time.time() - start

        assert elapsed < 1.0


class TestPathTraversalProtection:
    """Tests for path traversal attack prevention."""

    def test_path_traversal_blocked(self, tmp_path):
        """Path traversal attempts are blocked when loading."""
        from docwatch.serializer import PathTraversalError, _validate_path

        with pytest.raises(PathTraversalError):
            _validate_path("../../../../etc/passwd", tmp_path)

    def test_absolute_path_outside_base(self, tmp_path):
        """Absolute paths outside base are blocked."""
        from docwatch.serializer import PathTraversalError, _validate_path

        with pytest.raises(PathTraversalError):
            _validate_path("/etc/passwd", tmp_path)

    def test_valid_relative_path(self, tmp_path):
        """Valid relative paths are accepted."""
        from docwatch.serializer import _validate_path

        result = _validate_path("src/module.py", tmp_path)

        assert result == Path("src/module.py")
