"""
Centralized constants for the docwatch package.

This module contains:
- Filter sets for excluding common language constructs
- File extension mappings for language/format detection
- Directory ignore patterns for scanning
"""

# Python built-in functions commonly found in code examples
PYTHON_BUILTINS: frozenset[str] = frozenset({
    'print', 'len', 'str', 'int', 'float', 'bool', 'list', 'dict', 'set',
    'tuple', 'range', 'open', 'type', 'isinstance', 'issubclass', 'hasattr',
    'getattr', 'setattr', 'delattr', 'callable', 'iter', 'next', 'enumerate',
    'zip', 'map', 'filter', 'sorted', 'reversed', 'sum', 'min', 'max', 'abs',
    'round', 'pow', 'divmod', 'hex', 'oct', 'bin', 'ord', 'chr', 'repr',
    'hash', 'id', 'dir', 'vars', 'globals', 'locals', 'input', 'format',
    'slice', 'object', 'super', 'property', 'classmethod', 'staticmethod',
})

# Python keywords that appear in code but aren't meaningful identifiers
PYTHON_KEYWORDS: frozenset[str] = frozenset({
    'if', 'else', 'elif', 'for', 'while', 'try', 'except', 'finally',
    'with', 'as', 'def', 'class', 'return', 'yield', 'raise', 'import',
    'from', 'pass', 'break', 'continue', 'and', 'or', 'not', 'in', 'is',
    'lambda', 'global', 'nonlocal', 'assert', 'async', 'await', 'del',
})

# Common type hints that add noise to identifier extraction
PYTHON_COMMON_TYPES: frozenset[str] = frozenset({
    'True', 'False', 'None', 'Optional', 'List', 'Dict', 'Set', 'Tuple',
    'Union', 'Any', 'Callable', 'Type', 'Sequence', 'Mapping', 'Iterable',
    'Iterator', 'Generator', 'Path', 'Self',
})

# JavaScript/TypeScript builtins and keywords
JS_BUILTINS: frozenset[str] = frozenset({
    'console', 'log', 'warn', 'error', 'require', 'module', 'exports',
    'async', 'await', 'function', 'const', 'let', 'var', 'return',
    'if', 'else', 'for', 'while', 'try', 'catch', 'finally', 'throw',
    'new', 'this', 'class', 'extends', 'import', 'export', 'default',
    'true', 'false', 'null', 'undefined', 'typeof', 'instanceof',
    'Array', 'Object', 'String', 'Number', 'Boolean', 'Promise',
    'Map', 'Set', 'Date', 'JSON', 'Math', 'Error', 'RegExp',
})

# Combined filter sets for convenience
PYTHON_FILTER = PYTHON_BUILTINS | PYTHON_KEYWORDS
JS_FILTER = JS_BUILTINS

# Language aliases for code block detection
PYTHON_ALIASES = frozenset({'python', 'py', ''})
JS_ALIASES = frozenset({'javascript', 'js', 'typescript', 'ts'})

# Minimum identifier length to reduce false positives
MIN_IDENTIFIER_LENGTH = 3

# =============================================================================
# Module Path Constants
# =============================================================================

# Source directory prefixes to strip when computing module paths.
# These are removed to convert file paths like "src/mypackage/module.py"
# to module paths like "mypackage.module".
#
# Common conventions:
# - src/        Python src-layout (PEP 517/518)
# - lib/        Node.js, Ruby, some Python
# - source/     Alternative Python layout
# - pkg/        Go-style, some monorepos
# - packages/   Monorepo workspaces
# - app/        Rails, Django apps
SOURCE_DIR_PREFIXES: tuple[str, ...] = (
    "src",
    "lib",
    "source",
    "pkg",
    "packages",
    "app",
)

# =============================================================================
# File Scanner Constants
# =============================================================================

# Directories to ignore when scanning
DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset({
    '.git', '.hg', '.svn',              # Version control
    'node_modules', 'vendor',            # Dependencies
    '__pycache__', '.pytest_cache',      # Python cache
    'venv', '.venv', 'env', '.env',      # Virtual environments
    '.idea', '.vscode',                  # IDE configs
    'dist', 'build', 'target',           # Build outputs
    '.tox', '.nox',                      # Test runners
    'egg-info', '.eggs',                 # Python packaging
})

# Code file extensions
CODE_EXTENSIONS: frozenset[str] = frozenset({
    '.py', '.pyi', '.ipynb',             # Python + type stubs + notebooks
    '.js', '.ts', '.tsx', '.jsx',
    '.mjs', '.cjs',                      # ES/CommonJS modules
    '.php', '.rb', '.java', '.c', '.cpp',
    '.h', '.hpp', '.cs', '.go', '.rs',
    '.swift', '.kt', '.scala', '.sh',
    '.bash', '.zsh', '.fish', '.sql',
    '.html', '.css', '.scss', '.sass', '.tcss',
    '.vue', '.svelte', '.lua', '.r',
    '.m', '.mm', '.pl', '.pm',
    '.asp', '.aspx', '.jsp',             # Server-side scripting
    '.erb', '.ejs', '.twig',             # Template engines
    '.xsl', '.xslt',                     # XSL transformations
})

# Documentation file extensions
DOC_EXTENSIONS: frozenset[str] = frozenset({
    '.md', '.markdown',
    '.rst',
    '.txt',
    '.adoc', '.asciidoc',
    '.org',
    '.tex', '.latex',
})

# =============================================================================
# Language and Format Extension Mappings
# =============================================================================

# Map file extensions to language identifiers
LANGUAGE_EXTENSION_MAP: dict[str, str] = {
    '.py': 'python',
    '.pyi': 'python',
    '.js': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.jsx': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.go': 'go',
    '.rs': 'rust',
    '.java': 'java',
    '.php': 'php',
    '.rb': 'ruby',
}

# Map file extensions to documentation format identifiers
DOC_FORMAT_EXTENSION_MAP: dict[str, str] = {
    '.md': 'markdown',
    '.markdown': 'markdown',
    '.rst': 'restructuredtext',
    '.adoc': 'asciidoc',
    '.asciidoc': 'asciidoc',
    '.txt': 'plain',
}

# =============================================================================
# Documentation Extractor Constants
# =============================================================================

# Default language for code blocks without a specified language
DEFAULT_CODE_BLOCK_LANGUAGE = 'text'

# RST header underline characters (order determines precedence)
RST_UNDERLINE_CHARS = '=-~^"\'+:._#*'

# =============================================================================
# Analysis & Matching Constants
# =============================================================================

# Confidence scores for reference-to-entity matching
CONFIDENCE_EXACT_MATCH = 1.0           # Exact name match
CONFIDENCE_QUALIFIED_MATCH = 0.9       # Qualified name match (module.func)
CONFIDENCE_PARTIAL_QUALIFIED = 0.7     # Partial qualified match
CONFIDENCE_PARTIAL_MATCH = 0.5         # Substring match
CONFIDENCE_CODE_BLOCK_PENALTY = 0.6    # Multiplier for code block refs (weaker docs)

# Confidence scores for impact analysis (how certain we are docs need attention)
CONFIDENCE_BROKEN_REFERENCE = 1.0      # Entity deleted - docs definitely broken
CONFIDENCE_SIGNATURE_CHANGED = 0.8     # Signature changed - docs likely stale
CONFIDENCE_DOCSTRING_CHANGED = 0.6     # Docstring changed - docs may want to sync
CONFIDENCE_UNDOCUMENTED = 1.0          # New entity - definitely undocumented

# Fuzzy matching threshold for finding similar names
FUZZY_MATCH_CUTOFF = 0.6

# =============================================================================
# Priority Scoring Constants
# =============================================================================

# Base score for all issues
PRIORITY_BASE_SCORE = 0.5

# Entity type adjustments
PRIORITY_CLASS_BONUS = 0.2
PRIORITY_FUNCTION_BONUS = 0.1
PRIORITY_METHOD_PENALTY = 0.1

# Visibility adjustments
PRIORITY_PUBLIC_BONUS = 0.2
PRIORITY_PRIVATE_PENALTY = 0.3
PRIORITY_DUNDER_PENALTY = 0.3

# Reference location thresholds (line numbers)
LOCATION_PROMINENT_THRESHOLD = 20      # Very visible, near top of file
LOCATION_VISIBLE_THRESHOLD = 50        # Reasonably visible

# Reference location bonuses
PRIORITY_PROMINENT_BONUS = 0.2
PRIORITY_VISIBLE_BONUS = 0.1
PRIORITY_HEADER_BONUS = 0.2
PRIORITY_CODE_BLOCK_BONUS = 0.1
PRIORITY_SIMILAR_NAME_BONUS = 0.2

# =============================================================================
# Coverage Thresholds
# =============================================================================

# Coverage percentage thresholds for health assessment
COVERAGE_HEALTHY_THRESHOLD = 80        # >= this is "good" (green)
COVERAGE_WARNING_THRESHOLD = 50        # >= this is "okay" (yellow), below is "bad" (red)

# Priority thresholds for issue categorization
PRIORITY_HIGH_THRESHOLD = 0.7          # >= this is high priority
PRIORITY_MEDIUM_THRESHOLD = 0.4        # >= this is medium, below is low

# =============================================================================
# Serialization
# =============================================================================

# Version string for saved analysis files (for format compatibility)
ANALYSIS_FILE_VERSION = "1.0"
