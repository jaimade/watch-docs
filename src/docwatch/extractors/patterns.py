"""
Compiled regex patterns for code and documentation extraction.

All patterns use re.VERBOSE for readability and are pre-compiled for performance.
Patterns are grouped by the extractor that uses them.
"""
import re

# =============================================================================
# Python Patterns
# =============================================================================

PYTHON_FUNCTION_DEF = re.compile(
    r"""
    \b def \s+          # 'def' keyword with trailing whitespace
    (\w+)               # function name (captured)
    \s* \(              # optional whitespace, then opening paren
    """,
    re.VERBOSE,
)

PYTHON_CLASS_DEF = re.compile(
    r"""
    \b class \s+        # 'class' keyword with trailing whitespace
    (\w+)               # class name (captured)
    [\s(:]              # followed by whitespace, '(' or ':'
    """,
    re.VERBOSE,
)

# =============================================================================
# JavaScript/TypeScript Patterns
# =============================================================================

JS_FUNCTION_DECLARATION = re.compile(
    r"""
    \b (?:async \s+)?   # optional 'async' keyword
    function \s+        # 'function' keyword
    (\w+)               # function name (captured)
    \s* \(              # opening paren
    """,
    re.VERBOSE,
)

JS_ARROW_FUNCTION = re.compile(
    r"""
    \b (?:const|let|var) \s+    # variable declaration keyword
    (\w+)                        # variable name (captured)
    \s* = \s*                    # assignment
    (?:async \s+)?               # optional async
    (?:                          # either:
        \( [^)]* \)              #   parenthesized params
        |                        # or:
        [\w]+                    #   single param (no parens)
    )
    \s* =>                       # arrow
    """,
    re.VERBOSE,
)

JS_FUNCTION_EXPRESSION = re.compile(
    r"""
    \b (?:const|let|var) \s+    # variable declaration keyword
    (\w+)                        # variable name (captured)
    \s* = \s*                    # assignment
    (?:async \s+)?               # optional async
    function \s* \(              # function keyword and paren
    """,
    re.VERBOSE,
)

JS_CLASS_DEF = re.compile(
    r"""
    \b class \s+                           # 'class' keyword
    (\w+)                                   # class name (captured)
    (?:\s+ extends \s+ [\w.]+)?             # optional extends clause
    (?:\s+ implements \s+ [\w.,\s]+)?       # optional implements clause
    \s* \{                                  # opening brace
    """,
    re.VERBOSE,
)

JS_ES6_IMPORT = re.compile(
    r"""
    \b import \s+       # 'import' keyword
    .*?                 # import specifiers (non-greedy)
    \s+ from \s+        # 'from' keyword
    ['"] ([^'"]+) ['"]  # module path in quotes (captured)
    """,
    re.VERBOSE,
)

JS_SIDE_EFFECT_IMPORT = re.compile(
    r"""
    \b import \s+       # 'import' keyword (no 'from')
    ['"] ([^'"]+) ['"]  # module path in quotes (captured)
    """,
    re.VERBOSE,
)

JS_REQUIRE = re.compile(
    r"""
    \b require \s*      # 'require' keyword
    \( \s*              # opening paren
    ['"] ([^'"]+) ['"]  # module path in quotes (captured)
    \s* \)              # closing paren
    """,
    re.VERBOSE,
)

JS_DYNAMIC_IMPORT = re.compile(
    r"""
    \b import \s*       # 'import' as function
    \( \s*              # opening paren
    ['"] ([^'"]+) ['"]  # module path in quotes (captured)
    \s* \)              # closing paren
    """,
    re.VERBOSE,
)

JS_EXPORT_DECLARATION = re.compile(
    r"""
    \b export \s+                           # 'export' keyword
    (?:default \s+)?                         # optional 'default'
    (?:async \s+)?                           # optional 'async'
    (?:function|class|const|let|var) \s+    # declaration type
    (\w+)                                    # name (captured)
    """,
    re.VERBOSE,
)

JS_EXPORT_BRACES = re.compile(
    r"""
    \b export \s*       # 'export' keyword
    \{ ([^}]+) \}       # names in braces (captured)
    """,
    re.VERBOSE,
)

# =============================================================================
# Markdown Patterns
# =============================================================================

MARKDOWN_HEADER = re.compile(
    r"""
    ^                   # start of line
    (\#{1,6})           # 1-6 hash symbols (captured for level)
    \s+                 # required whitespace
    (.+)                # header text (captured)
    $                   # end of line
    """,
    re.VERBOSE,
)

MARKDOWN_FENCED_CODE_BLOCK = re.compile(
    r"""
    ^```(\w*)\n         # opening fence with optional language (captured)
    ((?:(?!^```).)*?)   # code content: non-greedy with negative lookahead to prevent backtracking
    ^```                # closing fence on its own line
    """,
    re.VERBOSE | re.MULTILINE | re.DOTALL,
)

MARKDOWN_INLINE_CODE = re.compile(
    r"""
    (?<!`)              # not preceded by backtick
    `                   # opening backtick
    ([^`]+)             # code content (captured)
    `                   # closing backtick
    (?!`)               # not followed by backtick
    """,
    re.VERBOSE,
)

MARKDOWN_LINK = re.compile(
    r"""
    \[                  # opening bracket
    ([^\]]+)            # link text (captured)
    \]                  # closing bracket
    \(                  # opening paren
    ([^)]+)             # URL (captured)
    \)                  # closing paren
    """,
    re.VERBOSE,
)

# Patterns for extracting identifiers from code blocks
CODE_PYTHON_FROM_IMPORT = re.compile(
    r"""
    ^ from \s+          # 'from' keyword at line start
    [\w.]+              # module path
    \s+ import \s+      # 'import' keyword
    (.+)                # imported names (captured)
    $                   # end of line
    """,
    re.VERBOSE | re.MULTILINE,
)

CODE_PYTHON_IMPORT = re.compile(
    r"""
    ^ import \s+        # 'import' keyword at line start
    ([\w.]+)            # module name (captured)
    """,
    re.VERBOSE | re.MULTILINE,
)

CODE_FUNCTION_CALL = re.compile(
    r"""
    \b                  # word boundary
    ([A-Za-z_]\w*)      # identifier (captured)
    \s* \(              # opening paren (possibly with whitespace)
    """,
    re.VERBOSE,
)

CODE_CLASS_NAME = re.compile(
    r"""
    \b                  # word boundary
    ([A-Z][A-Za-z0-9_]*) # PascalCase identifier (captured)
    \b                  # word boundary
    """,
    re.VERBOSE,
)

CODE_JS_DESTRUCTURE_IMPORT = re.compile(
    r"""
    import \s*          # 'import' keyword
    \{ ([^}]+) \}       # destructured names in braces (captured)
    """,
    re.VERBOSE,
)

CODE_WORD = re.compile(r"(\w+)")

# =============================================================================
# RST (reStructuredText) Patterns
# =============================================================================

RST_CODE_BLOCK_DIRECTIVE = re.compile(
    r"""
    \.\. \s+            # directive start
    code-block::        # 'code-block' directive
    \s* (\w*)           # optional language (captured)
    """,
    re.VERBOSE,
)

RST_INLINE_CODE = re.compile(
    r"""
    ``                  # opening double backticks
    ([^`]+)             # code content (captured)
    ``                  # closing double backticks
    """,
    re.VERBOSE,
)

RST_INLINE_LINK = re.compile(
    r"""
    `                   # opening backtick
    ([^<]+)             # link text (captured)
    \s+ <               # whitespace and opening angle bracket
    ([^>]+)             # URL (captured)
    >`_                 # closing angle bracket, backtick, underscore
    """,
    re.VERBOSE,
)

RST_REFERENCE_DEF = re.compile(
    r"""
    \.\. \s+            # directive start
    _                   # reference marker
    ([^:]+)             # reference name (captured)
    : \s+               # colon and whitespace
    (.+)                # URL (captured)
    """,
    re.VERBOSE,
)

# =============================================================================
# AsciiDoc Patterns
# =============================================================================

ASCIIDOC_HEADER = re.compile(
    r"""
    ^                   # start of line
    (={1,6})            # 1-6 equals signs (captured for level)
    \s+                 # required whitespace
    (.+)                # header text (captured)
    $                   # end of line
    """,
    re.VERBOSE,
)

ASCIIDOC_SOURCE_BLOCK = re.compile(
    r"""
    \[source            # source attribute
    ,? \s*              # optional comma
    (\w*)               # optional language (captured)
    \]                  # closing bracket
    """,
    re.VERBOSE,
)

ASCIIDOC_INLINE_CODE_BACKTICK = re.compile(
    r"""
    `                   # opening backtick
    ([^`]+)             # code content (captured)
    `                   # closing backtick
    """,
    re.VERBOSE,
)

ASCIIDOC_INLINE_CODE_PLUS = re.compile(
    r"""
    \+                  # opening plus
    ([^+]+)             # code content (captured)
    \+                  # closing plus
    """,
    re.VERBOSE,
)

ASCIIDOC_LINK = re.compile(
    r"""
    link:               # link macro
    ([^\[]+)            # URL (captured)
    \[                  # opening bracket
    ([^\]]*)            # link text (captured, may be empty)
    \]                  # closing bracket
    """,
    re.VERBOSE,
)

ASCIIDOC_URL_LINK = re.compile(
    r"""
    (?<!link:)          # not preceded by 'link:'
    (https?://[^\[]+)   # URL (captured)
    \[                  # opening bracket
    ([^\]]*)            # link text (captured, may be empty)
    \]                  # closing bracket
    """,
    re.VERBOSE,
)
