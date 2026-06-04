"""Pydantic request/response schemas for the API and the LLM tool contract."""
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Difficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


# ---- Inbound ----------------------------------------------------------------


class QuestionInput(BaseModel):
    """A single question the user wants distractors for."""

    question: str = Field(..., min_length=1, max_length=2000)
    correct_answer: str = Field(..., min_length=1, max_length=1000)
    num_distractors: int = Field(default=3, ge=1, le=5)
    difficulty: Difficulty = Difficulty.medium

    @field_validator("question", "correct_answer")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class GenerateRequest(BaseModel):
    """A batch of questions to process in one request."""

    questions: list[QuestionInput] = Field(..., min_length=1, max_length=200)
    # When true, run a second LLM pass that critiques each distractor and drops
    # any that are defensible-as-correct, ambiguous, or near-duplicates. Higher
    # quality, but roughly doubles cost and latency. Off by default.
    verify: bool = False


# ---- LLM tool output (what Claude must return per question) ------------------


class DistractorSet(BaseModel):
    """The structured shape Claude returns: only WRONG options + rationale.

    The correct answer is intentionally absent — it is added in code so it can
    never be altered by the model.
    """

    distractors: list[str] = Field(..., min_length=1, max_length=5)
    rationale: list[str] = Field(default_factory=list)


class DistractorVerdict(BaseModel):
    """The reviewer's judgment on one candidate distractor."""

    ok: bool
    # Short reason a distractor was rejected; empty when ok is True.
    issue: str = ""


class ReviewResult(BaseModel):
    """The structured shape the verification pass returns: one verdict per
    candidate distractor, parallel to the list it was given."""

    verdicts: list[DistractorVerdict] = Field(default_factory=list)


# ---- Outbound ---------------------------------------------------------------


class GeneratedQuestion(BaseModel):
    """One finished MCQ: the user's answer plus generated distractors, shuffled."""

    question: str
    correct_answer: str
    options: list[str]
    correct_index: int
    distractors: list[str]
    rationale: list[str] = Field(default_factory=list)
    difficulty: Difficulty
    error: str | None = None
    # True when the distractors passed through the optional verification pass.
    verified: bool = False


class GenerateResponse(BaseModel):
    results: list[GeneratedQuestion]
