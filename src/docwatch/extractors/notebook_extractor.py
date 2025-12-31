"""
Extract code entities from Jupyter notebooks (.ipynb files).

Jupyter notebooks are JSON files containing cells of code and markdown.
This extractor parses code cells and extracts Python entities from them.
"""
import json
import logging
from pathlib import Path
from typing import Optional

from docwatch.models import CodeEntity, EntityType, Location

logger = logging.getLogger(__name__)

__all__ = ["extract_from_notebook", "NotebookExtractor"]


class NotebookExtractor:
    """
    Extract code entities from Jupyter notebook files.

    Notebooks contain multiple code cells, each potentially defining
    functions, classes, and other entities. This extractor combines
    all code cells and extracts entities while tracking their cell locations.
    """

    def __init__(self, filepath: Path):
        self.filepath = filepath
        self.entities: list[CodeEntity] = []
        self.imports: list[str] = []

    def extract(self) -> tuple[list[CodeEntity], list[str]]:
        """
        Parse notebook and extract all entities from code cells.

        Returns:
            Tuple of (entities, imports)
        """
        try:
            content = self.filepath.read_text(encoding='utf-8')
            notebook = json.loads(content)
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Failed to read notebook %s: %s", self.filepath, e)
            return [], []

        # Validate notebook structure
        if not isinstance(notebook, dict):
            return [], []

        cells = notebook.get('cells', [])
        if not isinstance(cells, list):
            return [], []

        # Track cumulative line offset across cells
        line_offset = 0

        for cell_idx, cell in enumerate(cells):
            if not isinstance(cell, dict):
                continue

            cell_type = cell.get('cell_type', '')
            source = cell.get('source', [])

            # Handle source as list of lines or single string
            if isinstance(source, list):
                cell_source = ''.join(source)
                cell_lines = len(source)
            elif isinstance(source, str):
                cell_source = source
                cell_lines = source.count('\n') + 1
            else:
                continue

            if cell_type == 'code' and cell_source.strip():
                self._extract_from_cell(
                    cell_source,
                    cell_idx=cell_idx,
                    line_offset=line_offset
                )

            line_offset += cell_lines

        return self.entities, self.imports

    def _extract_from_cell(
        self,
        source: str,
        cell_idx: int,
        line_offset: int
    ) -> None:
        """Extract entities from a single code cell."""
        # Import here to avoid circular imports
        from docwatch.extractors.python_ast import PythonASTExtractor

        extractor = PythonASTExtractor(self.filepath)
        try:
            entities, imports = extractor.extract(source)
        except Exception as e:
            logger.debug("Failed to extract from cell %d in %s: %s", cell_idx, self.filepath, e)
            return

        # Adjust line numbers and add cell context
        for entity in entities:
            # Adjust line numbers to account for previous cells
            adjusted_entity = CodeEntity(
                name=entity.name,
                entity_type=entity.entity_type,
                location=Location(
                    file=self.filepath,
                    line_start=entity.location.line_start + line_offset,
                    line_end=(entity.location.line_end + line_offset
                              if entity.location.line_end else None),
                ),
                signature=entity.signature,
                docstring=entity.docstring,
                parent=entity.parent,
            )
            self.entities.append(adjusted_entity)

        # Collect imports (deduplicated)
        for imp in imports:
            if imp not in self.imports:
                self.imports.append(imp)


def extract_from_notebook(filepath: Path) -> tuple[list[CodeEntity], list[str]]:
    """
    Extract entities from a Jupyter notebook file.

    Args:
        filepath: Path to .ipynb file

    Returns:
        Tuple of (entities, imports)
    """
    extractor = NotebookExtractor(filepath)
    return extractor.extract()


def is_notebook(filepath: Path) -> bool:
    """Check if a file is a Jupyter notebook."""
    return filepath.suffix.lower() == '.ipynb'
