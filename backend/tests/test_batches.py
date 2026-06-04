"""Unit tests for batch (economy) generation with a mocked Batches API."""
from types import SimpleNamespace

import pytest

from app.batches import create_batch, poll_batch
from app.config import Settings
from app.models import QuestionInput

SETTINGS = Settings(anthropic_api_key="test", anthropic_model="test-model")


def _msg(distractors, rationale=None):
    block = SimpleNamespace(
        type="tool_use",
        name="submit_distractors",
        input={"distractors": distractors, "rationale": rationale or []},
    )
    return SimpleNamespace(content=[block])


def _entry(custom_id, *, type_="succeeded", message=None):
    return SimpleNamespace(
        custom_id=custom_id,
        result=SimpleNamespace(type=type_, message=message),
    )


class FakeBatches:
    def __init__(self, *, status="ended", entries=None):
        self._status = status
        self._entries = entries or []
        self.created_requests = None

    async def create(self, requests):
        self.created_requests = requests
        return SimpleNamespace(id="batch_123")

    async def retrieve(self, batch_id):
        succeeded = sum(1 for e in self._entries if e.result.type == "succeeded")
        return SimpleNamespace(
            id=batch_id,
            processing_status=self._status,
            request_counts=SimpleNamespace(
                succeeded=succeeded, errored=len(self._entries) - succeeded
            ),
        )

    async def results(self, batch_id):
        async def gen():
            for e in self._entries:
                yield e

        return gen()


class FakeClient:
    def __init__(self, batches):
        self.messages = SimpleNamespace(batches=batches)


def _q(question="Capital of Australia?", answer="Canberra", n=3):
    return QuestionInput(question=question, correct_answer=answer, num_distractors=n)


@pytest.mark.asyncio
async def test_create_batch_builds_one_request_per_question():
    fake = FakeBatches()
    client = FakeClient(fake)
    questions = [_q(), _q("2+2?", "4")]

    batch_id = await create_batch(client, SETTINGS, questions)

    assert batch_id == "batch_123"
    assert [r["custom_id"] for r in fake.created_requests] == ["0", "1"]
    assert fake.created_requests[0]["params"]["model"] == "test-model"
    assert fake.created_requests[0]["params"]["tool_choice"]["name"] == (
        "submit_distractors"
    )


@pytest.mark.asyncio
async def test_poll_in_progress_has_no_results():
    client = FakeClient(FakeBatches(status="in_progress", entries=[]))
    res = await poll_batch(client, SETTINGS, "batch_123", [_q()])

    assert res.done is False
    assert res.results is None
    assert res.total == 1


@pytest.mark.asyncio
async def test_poll_ended_assembles_results_in_order():
    entries = [
        _entry("0", message=_msg(["Sydney", "Melbourne", "Perth"], ["a", "b", "c"])),
        _entry("1", type_="errored"),
    ]
    client = FakeClient(FakeBatches(status="ended", entries=entries))
    questions = [_q(), _q("2+2?", "4")]

    res = await poll_batch(client, SETTINGS, "batch_123", questions)

    assert res.done is True
    assert res.results is not None and len(res.results) == 2
    # First succeeded: correct answer assembled in and present exactly once.
    first = res.results[0]
    assert first.error is None
    assert first.options[first.correct_index] == "Canberra"
    assert set(first.distractors) == {"Sydney", "Melbourne", "Perth"}
    # Second errored: surfaced as an errored question, answer preserved.
    assert res.results[1].error is not None
    assert res.results[1].options == ["4"]


@pytest.mark.asyncio
async def test_poll_drops_distractor_equal_to_answer():
    entries = [
        _entry("0", message=_msg(["Canberra", "Sydney", "Melbourne"]))
    ]
    client = FakeClient(FakeBatches(status="ended", entries=entries))
    res = await poll_batch(client, SETTINGS, "batch_123", [_q()])

    first = res.results[0]
    assert "Canberra" not in first.distractors
    assert first.options.count("Canberra") == 1  # only the assembled correct one
