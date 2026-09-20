from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class ReviewStatus(StrEnum):
    UNREVIEWED = "UNREVIEWED"
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


class ReviewDecision(StrEnum):
    CONFIRMED = "CONFIRMED"
    DISMISSED = "DISMISSED"


class ViolationReviewRequest(BaseModel):
    decision: ReviewDecision
    reason_code: str | None = Field(default=None, max_length=128)
    comment: str | None = Field(default=None, max_length=2000)
