import pytest
from pydantic import ValidationError

from app.models import Difficulty, GenerateRequest, QuestionInput
from app.prompts import (
    DISTRACTOR_TOOL,
    FULL_SYSTEM,
    TOOL_NAME,
    build_user_message,
)


def test_question_defaults():
    q = QuestionInput(question="Q?", correct_answer="A")
    assert q.num_distractors == 3
    assert q.difficulty == Difficulty.medium


def test_question_strips_whitespace():
    q = QuestionInput(question="  Q?  ", correct_answer="  A  ")
    assert q.question == "Q?"
    assert q.correct_answer == "A"


def test_blank_rejected():
    with pytest.raises(ValidationError):
        QuestionInput(question="   ", correct_answer="A")


def test_num_distractors_bounds():
    with pytest.raises(ValidationError):
        QuestionInput(question="Q?", correct_answer="A", num_distractors=0)
    with pytest.raises(ValidationError):
        QuestionInput(question="Q?", correct_answer="A", num_distractors=6)


def test_batch_requires_at_least_one():
    with pytest.raises(ValidationError):
        GenerateRequest(questions=[])


def test_tool_schema_excludes_correct_answer():
    props = DISTRACTOR_TOOL["input_schema"]["properties"]
    assert set(props) == {"distractors", "rationale", "misconceptions"}
    assert "correct_answer" not in props
    assert TOOL_NAME == "submit_distractors"


def test_user_message_includes_question_and_count():
    q = QuestionInput(
        question="Capital of France?",
        correct_answer="Paris",
        num_distractors=4,
        difficulty=Difficulty.hard,
    )
    msg = build_user_message(q)
    assert "Capital of France?" in msg
    assert "Paris" in msg
    assert "4 distractors" in msg
    assert "HARD" in msg


def test_system_prompt_has_key_rules():
    assert "unambiguously" in FULL_SYSTEM.lower()
    assert "homogeneous" in FULL_SYSTEM.lower()
    # few-shot present
    assert "Canberra" in FULL_SYSTEM
