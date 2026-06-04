"""Unit tests for question-from-text generation with a mocked Anthropic client."""
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.models import Difficulty
from app.questions import generate_questions

SETTINGS = Settings(anthropic_api_key="test", anthropic_model="test-model")


def _fake_questions_message(pairs):
    """pairs: list of (question, answer) tuples -> a submit_questions tool_use."""
    block = SimpleNamespace(
        type="tool_use",
        name="submit_questions",
        input={"questions": [{"question": q, "answer": a} for q, a in pairs]},
    )
    return SimpleNamespace(content=[block])


class FakeMessages:
    def __init__(self, message):
        self._message = message
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return self._message


class FakeClient:
    def __init__(self, message):
        self.messages = FakeMessages(message)


@pytest.mark.asyncio
async def test_maps_pairs_to_question_inputs():
    client = FakeClient(
        _fake_questions_message(
            [("What is the capital of Japan?", "Tokyo"), ("2 + 2?", "4")]
        )
    )
    out = await generate_questions(client, SETTINGS, "some text", 5, Difficulty.hard)

    assert len(out) == 2
    assert out[0].question == "What is the capital of Japan?"
    assert out[0].correct_answer == "Tokyo"
    # Difficulty is carried through; distractor count defaults sensibly.
    assert out[0].difficulty == Difficulty.hard
    assert out[0].num_distractors == 3


@pytest.mark.asyncio
async def test_dedupes_and_caps_to_count():
    client = FakeClient(
        _fake_questions_message(
            [
                ("Same question?", "A"),
                ("same QUESTION?", "B"),  # duplicate by normalized text
                ("Another?", "C"),
                ("Third?", "D"),
            ]
        )
    )
    out = await generate_questions(client, SETTINGS, "txt", 2, Difficulty.medium)

    questions = [q.question for q in out]
    assert questions == ["Same question?", "Another?"]  # dup dropped, capped at 2


@pytest.mark.asyncio
async def test_drops_blank_and_invalid_pairs():
    client = FakeClient(
        _fake_questions_message(
            [
                ("  ", "no question"),
                ("no answer?", "   "),
                ("X" * 5000, "too long question"),  # exceeds QuestionInput limit
                ("Good question?", "Good answer"),
            ]
        )
    )
    out = await generate_questions(client, SETTINGS, "txt", 5, Difficulty.easy)

    assert len(out) == 1
    assert out[0].question == "Good question?"
