"""Unit tests for the generator with a fully mocked Anthropic client."""
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.generator import _clean_distractors, generate_one
from app.models import QuestionInput

SETTINGS = Settings(anthropic_api_key="test", anthropic_model="test-model")


def _fake_message(distractors, rationale=None):
    """Build an object shaped like an Anthropic message with one tool_use block."""
    block = SimpleNamespace(
        type="tool_use",
        name="submit_distractors",
        input={"distractors": distractors, "rationale": rationale or []},
    )
    return SimpleNamespace(content=[block])


class FakeMessages:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        return self._responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.messages = FakeMessages(responses)


# ---- _clean_distractors -----------------------------------------------------


def test_clean_removes_correct_answer_case_insensitive():
    out = _clean_distractors(["paris", "London", "Rome"], "Paris", 3)
    assert "paris" not in [o.lower() for o in out if o.lower() == "paris"]
    assert out == ["London", "Rome"]


def test_clean_dedups_and_limits():
    out = _clean_distractors(["A", "a", "B", "C", "D"], "Z", 2)
    assert out == ["A", "B"]


def test_clean_drops_blanks():
    out = _clean_distractors(["  ", "B", ""], "Z", 5)
    assert out == ["B"]


# ---- generate_one -----------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_one_happy_path():
    client = FakeClient([_fake_message(["Sydney", "Melbourne", "Perth"],
                                       ["r1", "r2", "r3"])])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q)

    assert result.error is None
    assert len(result.options) == 4
    assert "Canberra" in result.options
    assert result.options[result.correct_index] == "Canberra"
    assert set(result.distractors) == {"Sydney", "Melbourne", "Perth"}


@pytest.mark.asyncio
async def test_generate_one_tops_up_when_short():
    # First call returns a distractor equal to the answer + one dup -> short.
    first = _fake_message(["Canberra", "Sydney", "Sydney"])
    second = _fake_message(["Melbourne", "Perth", "Darwin"])
    client = FakeClient([first, second])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q)

    assert result.error is None
    assert len(result.distractors) == 3
    assert "Canberra" not in result.distractors
    assert client.messages.calls == 2  # retried once


@pytest.mark.asyncio
async def test_generate_one_handles_api_error_gracefully():
    class Boom:
        messages = SimpleNamespace(
            create=lambda **k: (_ for _ in ()).throw(RuntimeError("api down"))
        )

    q = QuestionInput(question="Q?", correct_answer="A", num_distractors=3)
    result = await generate_one(Boom(), SETTINGS, q)

    assert result.error is not None
    assert "api down" in result.error
    assert result.options == ["A"]
    assert result.correct_index == 0
