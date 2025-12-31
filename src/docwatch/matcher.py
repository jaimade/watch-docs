"""
Reference matching for documentation analysis.

This module handles matching documentation references to code entities
using multiple strategies (exact, qualified, partial).

Performance optimizations:
- Trigram index for O(1) partial match candidate lookup
- Early termination on exact match
"""
import difflib
from collections import defaultdict

from docwatch.constants import (
    CONFIDENCE_CODE_BLOCK_PENALTY,
    CONFIDENCE_EXACT_MATCH,
    CONFIDENCE_PARTIAL_MATCH,
    CONFIDENCE_PARTIAL_QUALIFIED,
    CONFIDENCE_QUALIFIED_MATCH,
    FUZZY_MATCH_CUTOFF,
    MIN_IDENTIFIER_LENGTH,
)
from docwatch.models import CodeEntity, DocReference, LinkType, ReferenceType


def _extract_trigrams(text: str) -> set[str]:
    """
    Extract all 3-character sequences from text.

    Args:
        text: Input string

    Returns:
        Set of trigrams (3-char substrings)

    Example:
        _extract_trigrams("hello") -> {"hel", "ell", "llo"}
    """
    if len(text) < 3:
        return set()
    return {text[i:i+3].lower() for i in range(len(text) - 2)}


class ReferenceMatcher:
    """
    Matches documentation references to code entities.

    Uses multiple matching strategies with confidence scoring:
    - Exact: Reference text matches entity name exactly
    - Qualified: Reference like "module.func" matches entity "func"
    - Partial: Reference is substring of entity name or vice versa

    Performance: Uses trigram indexing for efficient partial matching.
    Instead of O(n) iteration over all entities, partial matching is
    O(1) lookup + O(k) verification where k << n.
    """

    def __init__(self, entity_index: dict[str, list[CodeEntity]]):
        """
        Initialize the matcher with pre-computed trigram index.

        Args:
            entity_index: Dict mapping entity names to lists of CodeEntity objects
        """
        self._entity_index = entity_index
        self._trigram_index = self._build_trigram_index()

    def _build_trigram_index(self) -> dict[str, set[str]]:
        """
        Build an inverted index mapping trigrams to entity names.

        This enables O(1) lookup of candidate names for partial matching.
        """
        index: dict[str, set[str]] = defaultdict(set)

        for name in self._entity_index:
            for trigram in _extract_trigrams(name):
                index[trigram].add(name)

        return dict(index)

    def _find_partial_candidates(self, text: str) -> set[str]:
        """
        Find entity names that might contain or be contained by text.

        Uses trigram intersection to find candidates in O(1) per trigram.

        Args:
            text: The search text

        Returns:
            Set of candidate entity names to check
        """
        trigrams = _extract_trigrams(text)

        if not trigrams:
            # Text too short for trigrams - fall back to all names
            # (but this is rare for MIN_IDENTIFIER_LENGTH >= 3)
            return set(self._entity_index.keys())

        # Find names that share at least one trigram
        candidates: set[str] = set()
        for trigram in trigrams:
            if trigram in self._trigram_index:
                candidates.update(self._trigram_index[trigram])

        return candidates

    def match(self, ref: DocReference) -> list[tuple[CodeEntity, LinkType, float]]:
        """
        Find code entities matching a reference.

        Args:
            ref: The documentation reference to match

        Returns:
            List of (entity, link_type, confidence) tuples.
            Code block references get a confidence penalty since
            they represent weaker documentation than inline prose.
        """
        clean_text = ref.clean_text
        matches = []

        # Code block references are weaker documentation
        confidence_multiplier = (
            CONFIDENCE_CODE_BLOCK_PENALTY
            if ref.reference_type == ReferenceType.CODE_BLOCK
            else 1.0
        )

        # Exact name match - O(1) lookup
        if clean_text in self._entity_index:
            for entity in self._entity_index[clean_text]:
                confidence = CONFIDENCE_EXACT_MATCH * confidence_multiplier
                matches.append((entity, LinkType.EXACT, confidence))
            return matches  # Exact match found, no need for fuzzy

        # Qualified match (e.g., "module.func" matches "func")
        if "." in clean_text:
            last_part = clean_text.split(".")[-1]
            if last_part in self._entity_index:
                for entity in self._entity_index[last_part]:
                    # Higher confidence if qualified name contains reference
                    if clean_text in entity.qualified_name:
                        confidence = CONFIDENCE_QUALIFIED_MATCH * confidence_multiplier
                        matches.append((entity, LinkType.QUALIFIED, confidence))
                    else:
                        confidence = CONFIDENCE_PARTIAL_QUALIFIED * confidence_multiplier
                        matches.append((entity, LinkType.PARTIAL, confidence))

        # Partial match (substring) - now O(k) instead of O(n)
        if not matches and len(clean_text) >= MIN_IDENTIFIER_LENGTH:
            # Get candidates via trigram index instead of iterating all names
            candidates = self._find_partial_candidates(clean_text)
            clean_lower = clean_text.lower()

            for name in candidates:
                name_lower = name.lower()
                # Check actual substring relationship
                if clean_lower in name_lower or name_lower in clean_lower:
                    for entity in self._entity_index[name]:
                        confidence = CONFIDENCE_PARTIAL_MATCH * confidence_multiplier
                        matches.append((entity, LinkType.PARTIAL, confidence))

        return matches

    def find_close_matches(
        self, text: str, cutoff: float = FUZZY_MATCH_CUTOFF
    ) -> list[str]:
        """
        Find entity names similar to the given text.

        Useful for detecting typos in documentation references.

        Args:
            text: The text to find similar matches for
            cutoff: Minimum similarity ratio (0.0 to 1.0)

        Returns:
            List of similar entity names
        """
        all_names = list(self._entity_index.keys())
        return difflib.get_close_matches(text, all_names, n=1, cutoff=cutoff)
