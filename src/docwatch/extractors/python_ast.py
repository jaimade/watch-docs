"""
Extract code entities from Python source using AST parsing.

This module provides accurate extraction that handles edge cases regex cannot:
- Code inside strings/comments is ignored
- Nested classes and methods are properly tracked
- Full signatures with type hints are captured
- Docstrings are extracted correctly

Memory efficient: Uses generators to yield entities without accumulating large lists.
"""
import ast
import logging
from pathlib import Path
from typing import Iterator, Optional

logger = logging.getLogger(__name__)

from docwatch.models import CodeEntity, EntityType, Location

__all__ = [
    "PythonASTExtractor",
    "extract_from_source",
    "extract_from_file",
    "iter_entities",
    "_detect_encoding",
]


class PythonASTExtractor:
    """
    Extract code entities from Python source using AST.

    Walks the syntax tree to find functions, classes, methods, and constants,
    capturing their signatures, docstrings, and locations.

    Uses generators internally for memory efficiency on large files.
    """

    def __init__(self, filepath: Path):
        self.filepath = filepath

    def extract(self, source: str) -> tuple[list[CodeEntity], list[str]]:
        """
        Parse source and extract all entities.

        Args:
            source: Python source code as string

        Returns:
            Tuple of (entities, imports)
        """
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.warning(
                "Syntax error in %s at line %s: %s",
                self.filepath, e.lineno, e.msg
            )
            return [], []

        # Consume generators into lists
        entities = list(self._iter_entities(tree))
        imports = list(self._iter_imports(tree))
        return entities, imports

    def extract_iter(self, source: str) -> Iterator[CodeEntity]:
        """
        Parse source and yield entities one at a time.

        Memory-efficient alternative to extract() for large files.
        Does not extract imports (use extract() if you need both).

        Args:
            source: Python source code as string

        Yields:
            CodeEntity objects as they are found
        """
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.warning(
                "Syntax error in %s at line %s: %s",
                self.filepath, e.lineno, e.msg
            )
            return

        yield from self._iter_entities(tree)

    def _iter_entities(
        self,
        node: ast.AST,
        class_stack: tuple[str, ...] = (),
        function_depth: int = 0,
    ) -> Iterator[CodeEntity]:
        """
        Recursively walk AST and yield entities.

        Args:
            node: Current AST node
            class_stack: Tuple of parent class names (immutable for generator safety)
            function_depth: How deep we are in function nesting
        """
        if isinstance(node, ast.Module):
            for child in node.body:
                yield from self._iter_entities(child, class_stack, function_depth)

        elif isinstance(node, ast.ClassDef):
            yield from self._handle_class(node, class_stack, function_depth)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield from self._handle_function(node, class_stack, function_depth)

        elif isinstance(node, ast.Assign):
            yield from self._handle_assign(node, class_stack, function_depth)

        elif isinstance(node, ast.AnnAssign):
            yield from self._handle_ann_assign(node, class_stack, function_depth)

        elif isinstance(node, ast.TypeAlias):
            yield from self._handle_type_alias(node, class_stack, function_depth)

    def _handle_class(
        self,
        node: ast.ClassDef,
        class_stack: tuple[str, ...],
        function_depth: int,
    ) -> Iterator[CodeEntity]:
        """Handle class definition and yield it plus its children."""
        parent = class_stack[-1] if class_stack else None
        decorators = self._extract_decorators(node)
        signature = self._build_class_signature(node, decorators)

        yield CodeEntity(
            name=node.name,
            entity_type=EntityType.CLASS,
            location=Location(
                file=self.filepath,
                line_start=node.lineno,
                line_end=node.end_lineno,
            ),
            signature=signature,
            docstring=ast.get_docstring(node),
            parent=parent,
        )

        # Recurse into class body with updated class stack
        new_class_stack = class_stack + (node.name,)
        for child in node.body:
            yield from self._iter_entities(child, new_class_stack, function_depth)

    def _handle_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        class_stack: tuple[str, ...],
        function_depth: int,
    ) -> Iterator[CodeEntity]:
        """Handle function/method definition."""
        parent = class_stack[-1] if class_stack else None
        entity_type = EntityType.METHOD if parent else EntityType.FUNCTION
        is_async = isinstance(node, ast.AsyncFunctionDef)

        decorators = self._extract_decorators(node)
        signature = self._build_function_signature(node, is_async, decorators)

        yield CodeEntity(
            name=node.name,
            entity_type=entity_type,
            location=Location(
                file=self.filepath,
                line_start=node.lineno,
                line_end=node.end_lineno,
            ),
            signature=signature,
            docstring=ast.get_docstring(node),
            parent=parent,
        )

        # Recurse into function body (for nested classes/functions)
        for child in node.body:
            yield from self._iter_entities(child, class_stack, function_depth + 1)

    def _handle_assign(
        self,
        node: ast.Assign,
        class_stack: tuple[str, ...],
        function_depth: int,
    ) -> Iterator[CodeEntity]:
        """Handle assignment - extract constants and type aliases."""
        if function_depth > 0:
            return  # Skip local variables

        parent = class_stack[-1] if class_stack else None

        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue

            name = target.id

            # Check for type alias (PascalCase = TypeExpression)
            if self._is_type_alias_name(name) and self._is_type_expression(node.value):
                yield self._make_type_alias_entity(
                    name, node.value, node.lineno, node.end_lineno, parent, is_explicit=False
                )
            # Check for constant (ALL_CAPS = value)
            elif self._is_constant_name(name):
                yield self._make_constant_entity(
                    name, None, node.value, node.lineno, node.end_lineno, parent
                )

    def _handle_ann_assign(
        self,
        node: ast.AnnAssign,
        class_stack: tuple[str, ...],
        function_depth: int,
    ) -> Iterator[CodeEntity]:
        """Handle annotated assignment."""
        if function_depth > 0:
            return

        if not isinstance(node.target, ast.Name):
            return

        parent = class_stack[-1] if class_stack else None
        name = node.target.id

        # Explicit TypeAlias annotation
        if self._is_type_alias_annotation(node.annotation) and node.value:
            yield self._make_type_alias_entity(
                name, node.value, node.lineno, node.end_lineno, parent, is_explicit=False
            )
        # Constant
        elif self._is_constant_name(name):
            yield self._make_constant_entity(
                name, node.annotation, node.value, node.lineno, node.end_lineno, parent
            )

    def _handle_type_alias(
        self,
        node: ast.TypeAlias,
        class_stack: tuple[str, ...],
        function_depth: int,
    ) -> Iterator[CodeEntity]:
        """Handle Python 3.12+ type alias (type X = Y)."""
        if function_depth > 0:
            return

        parent = class_stack[-1] if class_stack else None
        name = node.name.id if isinstance(node.name, ast.Name) else str(node.name)

        yield self._make_type_alias_entity(
            name, node.value, node.lineno, node.end_lineno, parent, is_explicit=True
        )

    def _make_type_alias_entity(
        self,
        name: str,
        value: ast.expr,
        lineno: int,
        end_lineno: Optional[int],
        parent: Optional[str],
        is_explicit: bool,
    ) -> CodeEntity:
        """Create a CodeEntity for a type alias."""
        value_str = self._unparse_safe(value)
        signature = f"type {name} = {value_str}" if is_explicit else f"{name} = {value_str}"

        return CodeEntity(
            name=name,
            entity_type=EntityType.VARIABLE,
            location=Location(
                file=self.filepath,
                line_start=lineno,
                line_end=end_lineno,
            ),
            signature=signature,
            docstring=None,
            parent=parent,
        )

    def _make_constant_entity(
        self,
        name: str,
        annotation: Optional[ast.expr],
        value: Optional[ast.expr],
        lineno: int,
        end_lineno: Optional[int],
        parent: Optional[str],
    ) -> CodeEntity:
        """Create a CodeEntity for a constant."""
        signature_parts = [name]
        if annotation:
            signature_parts.append(f": {self._unparse_safe(annotation)}")
        if value:
            signature_parts.append(f" = {self._unparse_safe(value)}")

        return CodeEntity(
            name=name,
            entity_type=EntityType.CONSTANT,
            location=Location(
                file=self.filepath,
                line_start=lineno,
                line_end=end_lineno,
            ),
            signature="".join(signature_parts),
            docstring=None,
            parent=parent,
        )

    def _iter_imports(self, tree: ast.Module) -> Iterator[str]:
        """Yield unique import module names."""
        seen: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_module = alias.name.split('.')[0]
                    if top_module not in seen:
                        seen.add(top_module)
                        yield top_module

            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_module = node.module.split('.')[0]
                    if top_module not in seen:
                        seen.add(top_module)
                        yield top_module

    # -------------------------------------------------------------------------
    # Dependency Analysis (unchanged - not a hot path)
    # -------------------------------------------------------------------------

    def extract_dependencies(self, source: str) -> dict[str, list[str]]:
        """
        Build a dependency map: which functions/methods call which others.

        Args:
            source: Python source code as string

        Returns:
            Dict mapping function names to lists of functions they call.
        """
        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            logger.warning(
                "Syntax error in %s at line %s: %s",
                self.filepath, e.lineno, e.msg
            )
            return {}

        defined_names = self._collect_defined_functions(tree)
        dependencies: dict[str, list[str]] = {}
        self._analyze_dependencies(tree, defined_names, dependencies, class_context=None)
        return dependencies

    def _collect_defined_functions(self, tree: ast.Module) -> set[str]:
        """Collect all function and method names defined in the module."""
        names: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                names.add(node.name)
            elif isinstance(node, ast.ClassDef):
                for child in ast.walk(node):
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        names.add(f"{node.name}.{child.name}")
                        names.add(child.name)

        return names

    def _analyze_dependencies(
        self,
        node: ast.AST,
        defined_names: set[str],
        dependencies: dict[str, list[str]],
        class_context: Optional[str],
    ) -> None:
        """Recursively analyze function bodies for calls."""
        if isinstance(node, ast.ClassDef):
            for child in node.body:
                self._analyze_dependencies(child, defined_names, dependencies, node.name)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = f"{class_context}.{node.name}" if class_context else node.name
            calls = self._find_calls_in_function(node, defined_names, class_context)
            if calls:
                dependencies[func_name] = sorted(set(calls))

        elif isinstance(node, ast.Module):
            for child in node.body:
                self._analyze_dependencies(child, defined_names, dependencies, class_context)

    def _find_calls_in_function(
        self,
        func_node: ast.FunctionDef | ast.AsyncFunctionDef,
        defined_names: set[str],
        class_context: Optional[str],
    ) -> list[str]:
        """Find all calls to defined functions within a function body."""
        calls = []
        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                call_name = self._extract_call_name(node, class_context)
                if call_name and call_name in defined_names:
                    calls.append(call_name)
        return calls

    def _extract_call_name(
        self,
        call_node: ast.Call,
        class_context: Optional[str],
    ) -> Optional[str]:
        """Extract the function name from a Call node."""
        func = call_node.func

        if isinstance(func, ast.Name):
            return func.id

        if isinstance(func, ast.Attribute):
            if isinstance(func.value, ast.Name):
                if func.value.id == "self" and class_context:
                    return f"{class_context}.{func.attr}"
                elif func.value.id == "cls" and class_context:
                    return f"{class_context}.{func.attr}"
                else:
                    return f"{func.value.id}.{func.attr}"

        return None

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _is_constant_name(self, name: str) -> bool:
        """Check if name follows ALL_CAPS constant convention."""
        if not name or not name[0].isupper():
            return False
        return all(c.isupper() or c.isdigit() or c == '_' for c in name)

    def _is_type_alias_annotation(self, annotation: ast.expr) -> bool:
        """Check if annotation is TypeAlias."""
        if isinstance(annotation, ast.Name) and annotation.id == "TypeAlias":
            return True
        if isinstance(annotation, ast.Attribute) and annotation.attr == "TypeAlias":
            return True
        return False

    def _is_type_expression(self, node: ast.expr) -> bool:
        """Heuristically check if an expression looks like a type."""
        if isinstance(node, ast.Name):
            name = node.id
            builtins = {'str', 'int', 'float', 'bool', 'bytes', 'list', 'dict',
                        'set', 'tuple', 'type', 'object', 'None'}
            if name in builtins:
                return True
            if name and name[0].isupper() and not name.isupper():
                return True
            return False

        if isinstance(node, ast.Subscript):
            return True

        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            return True

        if isinstance(node, ast.Constant) and node.value is None:
            return True

        return False

    def _is_type_alias_name(self, name: str) -> bool:
        """Check if name follows PascalCase type alias convention."""
        if not name or len(name) < 2:
            return False
        if not name[0].isupper():
            return False
        if name.isupper():
            return False
        return any(c.islower() for c in name)

    def _extract_decorators(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
    ) -> list[str]:
        """Extract decorator strings from a function or class."""
        return [self._unparse_safe(d) for d in node.decorator_list]

    def _build_function_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_async: bool,
        decorators: Optional[list[str]] = None,
    ) -> str:
        """Build string representation of function signature."""
        args_parts = []
        args = node.args

        num_defaults = len(args.defaults)
        num_args = len(args.args)
        first_default_idx = num_args - num_defaults

        for i, arg in enumerate(args.args):
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._unparse_safe(arg.annotation)}"
            default_idx = i - first_default_idx
            if 0 <= default_idx < len(args.defaults):
                arg_str += f" = {self._unparse_safe(args.defaults[default_idx])}"
            args_parts.append(arg_str)

        if args.vararg:
            vararg_str = f"*{args.vararg.arg}"
            if args.vararg.annotation:
                vararg_str += f": {self._unparse_safe(args.vararg.annotation)}"
            args_parts.append(vararg_str)
        elif args.kwonlyargs:
            args_parts.append("*")

        for i, arg in enumerate(args.kwonlyargs):
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._unparse_safe(arg.annotation)}"
            if i < len(args.kw_defaults) and args.kw_defaults[i] is not None:
                arg_str += f" = {self._unparse_safe(args.kw_defaults[i])}"
            args_parts.append(arg_str)

        if args.kwarg:
            kwarg_str = f"**{args.kwarg.arg}"
            if args.kwarg.annotation:
                kwarg_str += f": {self._unparse_safe(args.kwarg.annotation)}"
            args_parts.append(kwarg_str)

        return_annotation = ""
        if node.returns:
            return_annotation = f" -> {self._unparse_safe(node.returns)}"

        prefix = "async def" if is_async else "def"
        func_sig = f"{prefix} {node.name}({', '.join(args_parts)}){return_annotation}"

        if decorators:
            decorator_lines = "\n".join(f"@{d}" for d in decorators)
            return f"{decorator_lines}\n{func_sig}"
        return func_sig

    def _build_class_signature(
        self,
        node: ast.ClassDef,
        decorators: Optional[list[str]] = None,
    ) -> str:
        """Build class signature with base classes."""
        parts = []

        for base in node.bases:
            parts.append(self._unparse_safe(base))

        for keyword in node.keywords:
            if keyword.arg:
                parts.append(f"{keyword.arg}={self._unparse_safe(keyword.value)}")
            else:
                parts.append(f"**{self._unparse_safe(keyword.value)}")

        class_sig = f"class {node.name}({', '.join(parts)})" if parts else f"class {node.name}"

        if decorators:
            decorator_lines = "\n".join(f"@{d}" for d in decorators)
            return f"{decorator_lines}\n{class_sig}"
        return class_sig

    def _unparse_safe(self, node: ast.expr) -> str:
        """Safely convert AST node back to source code."""
        try:
            return ast.unparse(node)
        except Exception as e:
            logger.debug("Failed to unparse AST node %s: %s", type(node).__name__, e)
            return "..."


# -----------------------------------------------------------------------------
# Module-level convenience functions
# -----------------------------------------------------------------------------

def iter_entities(source: str, filepath: Path | None = None) -> Iterator[CodeEntity]:
    """
    Iterate over entities in Python source code.

    Memory-efficient generator that yields entities without building a list.

    Args:
        source: Python source code as string
        filepath: Optional path for location metadata

    Yields:
        CodeEntity objects as they are found
    """
    extractor = PythonASTExtractor(filepath or Path("<string>"))
    yield from extractor.extract_iter(source)


def extract_from_source(
    source: str,
    filepath: Path | None = None
) -> tuple[list[CodeEntity], list[str]]:
    """
    Extract entities from Python source code.

    Args:
        source: Python source code as string
        filepath: Optional path for location metadata

    Returns:
        Tuple of (entities, imports)
    """
    extractor = PythonASTExtractor(filepath or Path("<string>"))
    return extractor.extract(source)


def _detect_encoding(filepath: Path) -> str:
    """
    Detect the encoding of a Python file.

    Checks for:
    1. UTF-8 BOM
    2. PEP 263 coding declaration (# -*- coding: xxx -*-)
    3. Falls back to UTF-8
    """
    import re

    try:
        raw = filepath.read_bytes()
    except OSError as e:
        logger.debug("Cannot read %s for encoding detection, defaulting to utf-8: %s", filepath, e)
        return 'utf-8'

    if raw.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'

    coding_pattern = re.compile(rb'coding[:=]\s*([-\w.]+)')
    lines = raw.split(b'\n', 2)[:2]

    for line in lines:
        match = coding_pattern.search(line)
        if match:
            return match.group(1).decode('ascii')

    return 'utf-8'


def extract_from_file(filepath: Path) -> tuple[list[CodeEntity], list[str]]:
    """
    Extract entities from a Python file.

    Handles various encodings (UTF-8, BOM, PEP 263 declarations).

    Args:
        filepath: Path to Python file

    Returns:
        Tuple of (entities, imports)
    """
    encoding = _detect_encoding(filepath)

    try:
        source = filepath.read_text(encoding=encoding)
    except (OSError, UnicodeDecodeError) as e:
        logger.debug("Failed to read %s with %s encoding: %s", filepath, encoding, e)
        try:
            source = filepath.read_text(encoding='latin-1')
        except OSError as e:
            logger.warning("Failed to read %s: %s", filepath, e)
            return [], []

    extractor = PythonASTExtractor(filepath)
    return extractor.extract(source)
