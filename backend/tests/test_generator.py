"""Unit tests for the generator with a fully mocked Anthropic client."""
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.generator import _clean_distractors, generate_one, regenerate_partial
from app.models import KeptDistractor, QuestionInput

SETTINGS = Settings(anthropic_api_key="test", anthropic_model="test-model")


def _fake_message(distractors, rationale=None, misconceptions=None):
    """Build an object shaped like an Anthropic message with one tool_use block."""
    block = SimpleNamespace(
        type="tool_use",
        name="submit_distractors",
        input={
            "distractors": distractors,
            "rationale": rationale or [],
            "misconceptions": misconceptions or [],
        },
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


def _fake_check_message(ok, note=""):
    """Build a fake submit_answer_check tool_use message."""
    return SimpleNamespace(
        content=[
            SimpleNamespace(
                type="tool_use",
                name="submit_answer_check",
                input={"ok": ok, "note": note},
            )
        ]
    )


class RoutingFakeMessages:
    """Routes each create() to a canned response by the forced tool name, so the
    concurrent answer-check pass is deterministic regardless of scheduling."""

    def __init__(self, *, distractors, rationale, check, check_raises):
        self._distractors = distractors
        self._rationale = rationale or []
        self._check = check  # (ok, note)
        self._check_raises = check_raises
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        name = kwargs["tool_choice"]["name"]
        if name == "submit_answer_check":
            if self._check_raises:
                raise RuntimeError("check boom")
            return _fake_check_message(*self._check)
        return _fake_message(self._distractors, self._rationale)


class RoutingFakeClient:
    def __init__(
        self, distractors, rationale=None, check=(True, ""), check_raises=False
    ):
        self.messages = RoutingFakeMessages(
            distractors=distractors,
            rationale=rationale,
            check=check,
            check_raises=check_raises,
        )


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
async def test_generate_one_carries_misconceptions():
    client = FakeClient([
        _fake_message(
            ["Sydney", "Melbourne", "Perth"],
            ["r1", "r2", "r3"],
            ["Largest-city bias", "Former capital", "Distant city"],
        )
    ])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q)

    assert result.error is None
    assert len(result.misconceptions) == 3
    # Misconception label stays paired with its distractor.
    si = result.distractors.index("Melbourne")
    assert result.misconceptions[si] == "Former capital"


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


# ---- regenerate_partial -----------------------------------------------------


@pytest.mark.asyncio
async def test_regenerate_keeps_locked_and_fills_the_rest():
    # Two distractors locked; only one more should be generated.
    client = FakeClient([_fake_message(["Brisbane", "Darwin"], ["r", "r2"])])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    keep = [
        KeptDistractor(text="Sydney", rationale="biggest city"),
        KeptDistractor(text="Melbourne", rationale="former capital"),
    ]
    result = await regenerate_partial(client, SETTINGS, q, keep)

    assert result.error is None
    assert len(result.distractors) == 3
    assert "Sydney" in result.distractors and "Melbourne" in result.distractors
    # Kept rationale survives verbatim, paired to its distractor.
    si = result.distractors.index("Sydney")
    assert result.rationale[si] == "biggest city"
    assert client.messages.calls == 1  # asked for only the one missing distractor


@pytest.mark.asyncio
async def test_regenerate_preserves_kept_misconception():
    client = FakeClient([
        _fake_message(["Darwin"], ["r"], ["Distant city"])
    ])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=2)
    keep = [KeptDistractor(text="Melbourne", rationale="was capital",
                           misconception="Former capital")]
    result = await regenerate_partial(client, SETTINGS, q, keep)

    assert result.error is None
    mi = result.distractors.index("Melbourne")
    assert result.misconceptions[mi] == "Former capital"


@pytest.mark.asyncio
async def test_regenerate_excludes_candidates_matching_kept():
    # Model returns a kept value ("Sydney") plus a fresh one; the dup is dropped
    # and a top-up call fills the gap.
    client = FakeClient([
        _fake_message(["Sydney", "Perth"]),
        _fake_message(["Hobart", "Adelaide"]),
    ])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    keep = [
        KeptDistractor(text="Sydney"),
        KeptDistractor(text="Melbourne"),
    ]
    result = await regenerate_partial(client, SETTINGS, q, keep)

    assert result.error is None
    assert len(result.distractors) == 3
    # "Sydney" must appear exactly once (kept), never duplicated by generation.
    assert result.distractors.count("Sydney") == 1
    assert "Perth" in result.distractors


@pytest.mark.asyncio
async def test_regenerate_with_no_kept_is_a_full_regen():
    client = FakeClient([_fake_message(["Sydney", "Melbourne", "Perth"])])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await regenerate_partial(client, SETTINGS, q, [])

    assert result.error is None
    assert len(result.distractors) == 3
    assert "Canberra" in result.options


@pytest.mark.asyncio
async def test_regenerate_all_locked_makes_no_model_call():
    client = FakeClient([])  # no responses available — must not call the model
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=2)
    keep = [KeptDistractor(text="Sydney"), KeptDistractor(text="Melbourne")]
    result = await regenerate_partial(client, SETTINGS, q, keep)

    assert result.error is None
    assert set(result.distractors) == {"Sydney", "Melbourne"}
    assert client.messages.calls == 0


@pytest.mark.asyncio
async def test_regenerate_drops_kept_equal_to_correct_answer():
    # A kept value equal to the correct answer is discarded, so a replacement
    # is generated to reach the requested count.
    client = FakeClient([_fake_message(["Sydney", "Perth"])])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=2)
    keep = [
        KeptDistractor(text="Canberra"),  # equals the answer -> dropped
        KeptDistractor(text="Melbourne"),
    ]
    result = await regenerate_partial(client, SETTINGS, q, keep)

    assert result.error is None
    assert "Canberra" not in result.distractors
    assert "Melbourne" in result.distractors
    assert len(result.distractors) == 2


# ---- answer sanity-check ----------------------------------------------------


@pytest.mark.asyncio
async def test_answer_check_attached_when_ok():
    client = RoutingFakeClient(
        ["Sydney", "Melbourne", "Perth"], check=(True, "")
    )
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q, check_answer=True)

    assert result.error is None
    assert result.answer_check is not None
    assert result.answer_check.ok is True


@pytest.mark.asyncio
async def test_answer_check_flags_wrong_answer_without_changing_it():
    client = RoutingFakeClient(
        ["Tokyo", "Kyoto", "Yokohama"],
        check=(False, "The capital of Japan is Tokyo, not Osaka."),
    )
    q = QuestionInput(question="Capital of Japan?",
                      correct_answer="Osaka", num_distractors=3)
    result = await generate_one(client, SETTINGS, q, check_answer=True)

    assert result.error is None
    # Advisory only — the user's answer is untouched and still the correct one.
    assert result.correct_answer == "Osaka"
    assert result.options[result.correct_index] == "Osaka"
    assert result.answer_check is not None
    assert result.answer_check.ok is False
    assert "Tokyo" in result.answer_check.note


@pytest.mark.asyncio
async def test_answer_check_failure_is_swallowed():
    # The check call raises, but generation still succeeds with no verdict.
    client = RoutingFakeClient(
        ["Sydney", "Melbourne", "Perth"], check_raises=True
    )
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q, check_answer=True)

    assert result.error is None
    assert len(result.distractors) == 3
    assert result.answer_check is None


@pytest.mark.asyncio
async def test_no_answer_check_when_flag_off():
    client = RoutingFakeClient(["Sydney", "Melbourne", "Perth"])
    q = QuestionInput(question="Capital of Australia?",
                      correct_answer="Canberra", num_distractors=3)
    result = await generate_one(client, SETTINGS, q)  # check_answer defaults off

    assert result.answer_check is None
    assert client.messages.calls == 1  # generation only, no check call
