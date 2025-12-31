"""
Priority scoring for documentation issues.

This module assigns priority scores to documentation issues
(undocumented entities, broken references) based on multiple factors.
"""
from docwatch.constants import (
    LOCATION_PROMINENT_THRESHOLD,
    LOCATION_VISIBLE_THRESHOLD,
    PRIORITY_BASE_SCORE,
    PRIORITY_CLASS_BONUS,
    PRIORITY_CODE_BLOCK_BONUS,
    PRIORITY_DUNDER_PENALTY,
    PRIORITY_FUNCTION_BONUS,
    PRIORITY_HEADER_BONUS,
    PRIORITY_METHOD_PENALTY,
    PRIORITY_PRIVATE_PENALTY,
    PRIORITY_PROMINENT_BONUS,
    PRIORITY_PUBLIC_BONUS,
    PRIORITY_SIMILAR_NAME_BONUS,
    PRIORITY_VISIBLE_BONUS,
)
from docwatch.models import CodeEntity, DocReference, EntityType, ReferenceType
from docwatch.matcher import ReferenceMatcher


class PriorityScorer:
    """
    Scores documentation issues by priority.

    Uses multiple factors to determine urgency:
    - Entity type (class vs function)
    - Visibility (public vs private)
    - Location in documentation (prominent vs hidden)
    - Similarity to existing entities (potential typos)
    """

    def __init__(self, matcher: ReferenceMatcher):
        """
        Initialize the scorer.

        Args:
            matcher: ReferenceMatcher for finding similar entity names
        """
        self._matcher = matcher

    def score_issue(self, item, issue_type: str) -> tuple[float, str]:
        """
        Calculate priority score for an issue.

        Args:
            item: Either a CodeEntity (for undocumented) or DocReference (for broken)
            issue_type: "undocumented" or "broken_reference"

        Returns:
            Tuple of (priority_score, reason_string)
            - priority_score: float from 0.0 (low) to 1.0 (critical)
            - reason_string: explanation of why this priority was assigned
        """
        if issue_type == "undocumented":
            return self.score_undocumented_entity(item)
        else:
            return self.score_broken_reference(item)

    def score_undocumented_entity(self, entity: CodeEntity) -> tuple[float, str]:
        """
        Score an undocumented code entity.

        Higher scores for:
        - Classes (more important than functions)
        - Public API (no underscore prefix)
        - Standalone entities (not methods)

        Lower scores for:
        - Private entities (underscore prefix)
        - Methods inside classes
        - Dunder methods (__init__, __str__, etc.)

        Args:
            entity: The undocumented code entity

        Returns:
            Tuple of (score, reason)
        """
        score = PRIORITY_BASE_SCORE
        reasons = []

        # Classes are more important than functions
        if entity.entity_type == EntityType.CLASS:
            score += PRIORITY_CLASS_BONUS
            reasons.append("class")
        elif entity.entity_type == EntityType.FUNCTION:
            score += PRIORITY_FUNCTION_BONUS
            reasons.append("function")

        # Public vs private (underscore prefix)
        if entity.name.startswith("_"):
            score -= PRIORITY_PRIVATE_PENALTY
            reasons.append("private")
        else:
            score += PRIORITY_PUBLIC_BONUS
            reasons.append("public API")

        # Methods inside classes are slightly less urgent than standalone
        if entity.parent:
            score -= PRIORITY_METHOD_PENALTY
            reasons.append(f"method of {entity.parent}")

        # Dunder methods are low priority (usually self-documenting)
        if entity.name.startswith("__") and entity.name.endswith("__"):
            score -= PRIORITY_DUNDER_PENALTY
            reasons.append("dunder method")

        # Clamp score to valid range
        score = max(0.0, min(1.0, score))

        reason = f"Undocumented {', '.join(reasons)}"
        return (round(score, 2), reason)

    def score_broken_reference(self, ref: DocReference) -> tuple[float, str]:
        """
        Score a broken documentation reference.

        Higher scores for:
        - Prominent location (near top of file)
        - Header references (more visible)
        - Similar to existing entities (likely typos)

        Args:
            ref: The broken documentation reference

        Returns:
            Tuple of (score, reason)
        """
        score = PRIORITY_BASE_SCORE
        reasons = []

        # References early in file are more visible
        if ref.location.line_start <= LOCATION_PROMINENT_THRESHOLD:
            score += PRIORITY_PROMINENT_BONUS
            reasons.append("prominent location")
        elif ref.location.line_start <= LOCATION_VISIBLE_THRESHOLD:
            score += PRIORITY_VISIBLE_BONUS
            reasons.append("visible location")

        # Headers are more important than inline code
        if ref.reference_type == ReferenceType.HEADER:
            score += PRIORITY_HEADER_BONUS
            reasons.append("in header")
        elif ref.reference_type == ReferenceType.CODE_BLOCK:
            score += PRIORITY_CODE_BLOCK_BONUS
            reasons.append("in code block")

        # Check if reference looks like it might be a typo of existing entity
        close_matches = self._matcher.find_close_matches(ref.clean_text)
        if close_matches:
            score += PRIORITY_SIMILAR_NAME_BONUS
            reasons.append(f"similar to '{close_matches[0]}'")

        # Clamp score to valid range
        score = max(0.0, min(1.0, score))

        reason = f"Broken reference: {', '.join(reasons)}" if reasons else "Broken reference"
        return (round(score, 2), reason)
