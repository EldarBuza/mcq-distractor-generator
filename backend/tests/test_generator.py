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


def _fake_review(oks):
    """Build a fake submit_review message: one verdict per bool in `oks`."""
    block = SimpleNamespace(
        type="tool_use",
        name="submit_review",
        input={
            "verdicts": [
                {"ok": ok, "issue": "" if ok else "not a good distractor"}
                for ok in oks
            ]
        },
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


# ---- generate_one with verification ----------------------------------------


@pytest.mark.asyncio
async def test_verify_keeps_all_when_all_ok():
    client = FakeClient([
        _fake_message(["Sydney", "Melbourne", "Perth"], ["r1", "r2", "r3"]),
        _fake_review([True, True, True]),
    ])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q, verify=True)

    assert result.error is None
    assert result.verified is True
    assert set(result.distractors) == {"Sydney", "Melbourne", "Perth"}
    assert client.messages.calls == 2  # generate + review, no replenish


@pytest.mark.asyncio
async def test_verify_drops_then_replenishes():
    client = FakeClient([
        _fake_message(["Sydney", "Melbourne", "Perth"], ["r1", "r2", "r3"]),
        _fake_review([True, True, False]),  # rejects "Perth"
        _fake_message(["Darwin", "Hobart", "Adelaide"], ["r4", "r5", "r6"]),
        _fake_review([True]),  # accepts the one top-up candidate we need
    ])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q, verify=True)

    assert result.error is None
    assert result.verified is True
    assert len(result.distractors) == 3
    assert "Perth" not in result.distractors
    assert "Darwin" in result.distractors
    assert client.messages.calls == 4  # generate + review + replenish + review


@pytest.mark.asyncio
async def test_verify_rejecting_all_yields_error():
    client = FakeClient([
        _fake_message(["Sydney", "Melbourne", "Perth"], ["r1", "r2", "r3"]),
        _fake_review([False, False, False]),
    ])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q, verify=True)

    assert result.error is not None
    assert "survived verification" in result.error
    assert result.options == ["Canberra"]


@pytest.mark.asyncio
async def test_verify_off_skips_review_call():
    client = FakeClient([_fake_message(["Sydney", "Melbourne", "Perth"])])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q)  # verify defaults False

    assert result.error is None
    assert result.verified is False
    assert client.messages.calls == 1  # generate only, no review


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
