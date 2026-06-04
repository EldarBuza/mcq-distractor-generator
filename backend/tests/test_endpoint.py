"""Tests for the /generate endpoint (Anthropic calls mocked).

These tests control app.state.anthropic explicitly so they pass whether or not
a real key is present in the environment.
"""
import app.main as main
from app.models import Difficulty, GeneratedQuestion
from fastapi.testclient import TestClient


class FakeClient:
    """Stands in for AsyncAnthropic; satisfies the lifespan teardown's close()."""

    async def close(self):
        pass


def _sample_payload():
    return {
        "questions": [
            {"question": "Capital of Australia?", "correct_answer": "Canberra"}
        ]
    }


def test_generate_503_without_client():
    with TestClient(main.app) as client:
        main.app.state.anthropic = None  # simulate "no key configured"
        resp = client.post("/generate", json=_sample_payload())
    assert resp.status_code == 503
    assert "ANTHROPIC_API_KEY" in resp.json()["detail"]


def test_generate_validation_error_empty_batch():
    with TestClient(main.app) as client:
        resp = client.post("/generate", json={"questions": []})
    assert resp.status_code == 422


def test_generate_happy_path(monkeypatch):
    async def fake_batch(client, settings, questions, verify=False):
        return [
            GeneratedQuestion(
                question=q.question,
                correct_answer=q.correct_answer,
                options=[q.correct_answer, "X", "Y", "Z"],
                correct_index=0,
                distractors=["X", "Y", "Z"],
                rationale=["r1", "r2", "r3"],
                difficulty=Difficulty.medium,
                verified=verify,
            )
            for q in questions
        ]

    monkeypatch.setattr(main, "generate_batch", fake_batch)

    with TestClient(main.app) as client:
        main.app.state.anthropic = FakeClient()  # non-None: pass the 503 guard
        resp = client.post("/generate", json=_sample_payload())

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["results"]) == 1
    r = body["results"][0]
    assert r["correct_answer"] == "Canberra"
    assert r["options"][r["correct_index"]] == "Canberra"
    assert r["error"] is None
    assert r["verified"] is False  # verify defaults off


def test_generate_passes_verify_flag(monkeypatch):
    """The endpoint must forward request.verify into generate_batch."""
    seen = {}

    async def fake_batch(client, settings, questions, verify=False):
        seen["verify"] = verify
        return [
            GeneratedQuestion(
                question=q.question,
                correct_answer=q.correct_answer,
                options=[q.correct_answer, "X", "Y", "Z"],
                correct_index=0,
                distractors=["X", "Y", "Z"],
                rationale=[],
                difficulty=Difficulty.medium,
                verified=verify,
            )
            for q in questions
        ]

    monkeypatch.setattr(main, "generate_batch", fake_batch)

    payload = _sample_payload()
    payload["verify"] = True
    with TestClient(main.app) as client:
        main.app.state.anthropic = FakeClient()
        resp = client.post("/generate", json=payload)

    assert resp.status_code == 200
    assert seen["verify"] is True
    assert resp.json()["results"][0]["verified"] is True
