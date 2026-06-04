"""Asynchronous "economy" generation via the Anthropic Message Batches API.

Batches are ~50% cheaper but non-realtime (minutes, occasionally up to 24h) and
one-shot per question — so this path is single-pass: it generates distractors
once, then cleans + assembles in code. The verify / answer-check / top-up passes
of the synchronous path do not apply here.

The app stays stateless: the original questions are passed back when polling so
results can be assembled (correct answer added in code, then shuffled) — the
correct-answer guarantee is preserved exactly as in the sync path.
"""
import random

from anthropic import AsyncAnthropic

from app.config import Settings
from app.generator import _clean_distractors, _extract_tool_input
from app.models import (
    BatchStatusResponse,
    DistractorSet,
    GeneratedQuestion,
    QuestionInput,
)
from app.prompts import DISTRACTOR_TOOL, FULL_SYSTEM, TOOL_NAME, build_user_message

MAX_TOKENS = 1024


def _request_for(index: int, q: QuestionInput) -> dict:
    """One batch request; custom_id is the question's index in the submission."""
    return {
        "custom_id": str(index),
        "params": {
            "model": None,  # filled in by create_batch from settings
            "max_tokens": MAX_TOKENS,
            "system": [
                {
                    "type": "text",
                    "text": FULL_SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tools": [DISTRACTOR_TOOL],
            "tool_choice": {"type": "tool", "name": TOOL_NAME},
            "messages": [{"role": "user", "content": build_user_message(q)}],
        },
    }


async def create_batch(
    client: AsyncAnthropic, settings: Settings, questions: list[QuestionInput]
) -> str:
    """Submit one distractor-generation request per question; return the batch id."""
    requests = []
    for i, q in enumerate(questions):
        req = _request_for(i, q)
        req["params"]["model"] = settings.anthropic_model
        requests.append(req)
    batch = await client.messages.batches.create(requests=requests)
    return batch.id


def _assemble(q: QuestionInput, dset: DistractorSet) -> GeneratedQuestion:
    """Clean the model's distractors and assemble a finished MCQ (correct answer
    added in code, options shuffled). Mirrors the sync path's assembly."""
    distractors = _clean_distractors(
        dset.distractors, q.correct_answer, q.num_distractors
    )
    if not distractors:
        return _errored(q, "no usable distractors after cleaning")
    rationale = dset.rationale[: len(distractors)]
    options = [q.correct_answer] + distractors
    random.shuffle(options)
    return GeneratedQuestion(
        question=q.question,
        correct_answer=q.correct_answer,
        options=options,
        correct_index=options.index(q.correct_answer),
        distractors=distractors,
        rationale=rationale,
        difficulty=q.difficulty,
    )


def _errored(q: QuestionInput, message: str) -> GeneratedQuestion:
    return GeneratedQuestion(
        question=q.question,
        correct_answer=q.correct_answer,
        options=[q.correct_answer],
        correct_index=0,
        distractors=[],
        rationale=[],
        difficulty=q.difficulty,
        error=message,
    )


async def poll_batch(
    client: AsyncAnthropic,
    settings: Settings,
    batch_id: str,
    questions: list[QuestionInput],
) -> BatchStatusResponse:
    """Report a batch's status; once ended, fetch and assemble its results in the
    submitted order. Per-request failures become errored questions, so the list
    always lines up 1:1 with the input."""
    batch = await client.messages.batches.retrieve(batch_id)
    counts = batch.request_counts
    total = len(questions)
    base = BatchStatusResponse(
        batch_id=batch_id,
        status=batch.processing_status,
        done=batch.processing_status == "ended",
        succeeded=counts.succeeded,
        errored=counts.errored,
        total=total,
    )
    if not base.done:
        return base

    # Collect results by custom_id (order from the API is not guaranteed).
    by_id: dict[str, object] = {}
    stream = await client.messages.batches.results(batch_id)
    async for entry in stream:
        by_id[entry.custom_id] = entry

    results: list[GeneratedQuestion] = []
    for i, q in enumerate(questions):
        entry = by_id.get(str(i))
        if entry is None or entry.result.type != "succeeded":
            results.append(_errored(q, "batch request did not succeed"))
            continue
        try:
            dset = _extract_tool_input(entry.result.message, TOOL_NAME, DistractorSet)
            results.append(_assemble(q, dset))
        except Exception as exc:  # noqa: BLE001
            results.append(_errored(q, f"{type(exc).__name__}: {exc}"))

    base.results = results
    return base
