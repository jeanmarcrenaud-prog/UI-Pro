# core/code_review.py - Backward Compatibility Re-export
#
# DEPRECATED: Import from backend.domain.core.code_review instead

from backend.domain.core.code_review import (
    ReviewResult,
    CodeReviewer,
    get_reviewer,
    review_code,
)

__all__ = [
    "ReviewResult",
    "CodeReviewer",
    "get_reviewer",
    "review_code",
]