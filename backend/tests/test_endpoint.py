"""Tests for the /generate endpoint (Anthropic calls mocked).

These tests control app.state.anthropic explicitly so they pass whether or not
a real key is present in the environment.
"""
import app.main as main
from app.models import Difficulty, GeneratedQuestion, QuestionInput
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
    async def fake_batch(client, settings, questions, verify=False,
                         check_answer=False):
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

    async def fake_batch(client, settings, questions, verify=False,
                         check_answer=False):
        seen["verify"] = verify
        seen["check_answer"] = check_answer
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
    payload["check_answer"] = True
    with TestClient(main.app) as client:
        main.app.state.anthropic = FakeClient()
        resp = client.post("/generate", json=payload)

    assert resp.status_code == 200
    assert seen["verify"] is True
    assert seen["check_answer"] is True
    assert resp.json()["results"][0]["verified"] is True


def test_regenerate_503_without_client():
    with TestClient(main.app) as client:
        main.app.state.anthropic = None
        resp = client.post(
            "/regenerate",
            json={"question": {"question": "Q?", "correct_answer": "A"}},
        )
    assert resp.status_code == 503


def test_regenerate_forwards_question_and_keep(monkeypatch):
    seen = {}

    async def fake_regen(client, settings, question, keep, verify=False):
        seen["keep"] = [k.text for k in keep]
        seen["verify"] = verify
        return GeneratedQuestion(
            question=question.question,
            correct_answer=question.correct_answer,
            options=[question.correct_answer, "Sydney", "X"],
            correct_index=0,
            distractors=["Sydney", "X"],
            rationale=["kept", "new"],
            difficulty=Difficulty.medium,
            verified=verify,
        )

    monkeypatch.setattr(main, "regenerate_partial", fake_regen)

    payload = {
        "question": {
            "question": "Capital of Australia?",
            "correct_answer": "Canberra",
            "num_distractors": 2,
        },
        "keep": [{"text": "Sydney", "rationale": "kept"}],
        "verify": True,
    }
    with TestClient(main.app) as client:
        main.app.state.anthropic = FakeClient()
        resp = client.post("/regenerate", json=payload)

    assert resp.status_code == 200
    assert seen["keep"] == ["Sydney"]
    assert seen["verify"] is True
    body = resp.json()
    assert body["correct_answer"] == "Canberra"
    assert "Sydney" in body["distractors"]


def test_generate_questions_503_without_client():
    with TestClient(main.app) as client:
        main.app.state.anthropic = None
        resp = client.post("/generate-questions", json={"text": "some text"})
    assert resp.status_code == 503


def test_generate_questions_happy_path(monkeypatch):
    seen = {}

    async def fake_gen_questions(client, settings, text, count, difficulty):
        seen["text"] = text
        seen["count"] = count
        seen["difficulty"] = difficulty
        return [
            QuestionInput(
                question="Capital of Japan?",
                correct_answer="Tokyo",
                num_distractors=3,
                difficulty=difficulty,
            )
        ]

    monkeypatch.setattr(main, "generate_questions", fake_gen_questions)

    payload = {"text": "Tokyo is the capital of Japan.", "count": 3,
               "difficulty": "hard"}
    with TestClient(main.app) as client:
        main.app.state.anthropic = FakeClient()
        resp = client.post("/generate-questions", json=payload)

    assert resp.status_code == 200
    assert seen["count"] == 3
    assert seen["difficulty"] == Difficulty.hard
    body = resp.json()
    assert len(body["questions"]) == 1
    assert body["questions"][0]["correct_answer"] == "Tokyo"


def test_generate_questions_validation_rejects_empty_text():
    with TestClient(main.app) as client:
        resp = client.post("/generate-questions", json={"text": ""})
    assert resp.status_code == 422
