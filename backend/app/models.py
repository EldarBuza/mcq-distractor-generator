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
    # When true, run an advisory pass that judges whether the supplied
    # correct_answer is actually correct for the question. Never changes the
    # answer — it only attaches a warning. Off by default.
    check_answer: bool = False


class GenerateQuestionsRequest(BaseModel):
    """Generate question + correct-answer pairs from a block of source text."""

    text: str = Field(..., min_length=1, max_length=20_000)
    count: int = Field(default=5, ge=1, le=20)
    difficulty: Difficulty = Difficulty.medium


class QuestionsResponse(BaseModel):
    """The question + answer pairs drafted from source text, ready to edit and
    feed into distractor generation."""

    questions: list[QuestionInput] = Field(default_factory=list)


class KeptDistractor(BaseModel):
    """A distractor the user locked, carried through a partial regeneration so
    its text and rationale survive verbatim."""

    text: str = Field(..., min_length=1, max_length=1000)
    rationale: str = ""


class RegenerateRequest(BaseModel):
    """Regenerate only the UNLOCKED distractors of one question, keeping the
    locked ones. New distractors are generated to avoid duplicating the kept
    set, then everything is reassembled and reshuffled around the correct answer."""

    question: QuestionInput
    keep: list[KeptDistractor] = Field(default_factory=list)
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


class AnswerCheck(BaseModel):
    """Advisory verdict on whether the supplied correct answer is actually
    correct. Doubles as the answer-check tool's output schema and the field
    attached to a finished question. Purely informational — never mutates."""

    ok: bool
    # Short explanation when ok is False (why the answer looks wrong); may also
    # carry a brief confirmation when ok is True.
    note: str = ""


class QuestionDraft(BaseModel):
    """One question + correct-answer pair drafted from source text (no options)."""

    question: str
    answer: str


class QuestionDraftSet(BaseModel):
    """The structured shape the question-from-text pass returns."""

    questions: list[QuestionDraft] = Field(default_factory=list)


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
    # Advisory result of the optional answer sanity-check; None when not run.
    answer_check: AnswerCheck | None = None


class GenerateResponse(BaseModel):
    results: list[GeneratedQuestion]
