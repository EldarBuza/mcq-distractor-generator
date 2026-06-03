"""Core distractor generation: call Claude, validate, assemble, shuffle.

The correct answer is added to the option list HERE, in code — never by the
model — so the user's answer is guaranteed to survive verbatim.
"""
import asyncio
import random

from anthropic import AsyncAnthropic
from pydantic import ValidationError

from app.config import Settings
from app.models import DistractorSet, GeneratedQuestion, QuestionInput
from app.prompts import (
    DISTRACTOR_TOOL,
    FULL_SYSTEM,
    TOOL_NAME,
    build_user_message,
)

MAX_TOKENS = 1024

# Cap concurrent in-flight requests to the Anthropic API per batch, so a large
# upload doesn't trip rate limits.
MAX_CONCURRENCY = 8


def _norm(s: str) -> str:
    """Normalize for equality checks: case- and whitespace-insensitive."""
    return " ".join(s.lower().split())


def _clean_distractors(
    raw: list[str], correct_answer: str, limit: int
) -> list[str]:
    """Drop blanks, anything equal to the correct answer, and duplicates."""
    correct_n = _norm(correct_answer)
    seen: set[str] = set()
    out: list[str] = []
    for d in raw:
        d = d.strip()
        if not d:
            continue
        n = _norm(d)
        if n == correct_n or n in seen:
            continue
        seen.add(n)
        out.append(d)
        if len(out) >= limit:
            break
    return out


def _extract_distractor_set(message) -> DistractorSet:
    """Pull the tool_use input out of an Anthropic message and validate it."""
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == TOOL_NAME:
            return DistractorSet.model_validate(block.input)
    raise ValueError("model did not call the submit_distractors tool")


async def _call_model(
    client: AsyncAnthropic, settings: Settings, q: QuestionInput
) -> DistractorSet:
    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": FULL_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[DISTRACTOR_TOOL],
        tool_choice={"type": "tool", "name": TOOL_NAME},
        messages=[{"role": "user", "content": build_user_message(q)}],
    )
    return _extract_distractor_set(message)


async def generate_one(
    client: AsyncAnthropic, settings: Settings, q: QuestionInput
) -> GeneratedQuestion:
    """Generate distractors for one question and return a finished MCQ.

    On any failure, returns a GeneratedQuestion with `error` set and the correct
    answer as the sole option, so a batch never fails wholesale.
    """
    try:
        result = await _call_model(client, settings, q)
        distractors = _clean_distractors(
            result.distractors, q.correct_answer, q.num_distractors
        )

        # If dedup left us short, make one top-up attempt.
        if len(distractors) < q.num_distractors:
            retry = await _call_model(client, settings, q)
            merged = distractors + retry.distractors
            distractors = _clean_distractors(
                merged, q.correct_answer, q.num_distractors
            )

        if not distractors:
            raise ValueError("no usable distractors after cleaning")

        # Pair rationale to surviving distractors by best-effort index alignment.
        rationale = result.rationale[: len(distractors)]

        options = [q.correct_answer] + distractors
        random.shuffle(options)
        correct_index = options.index(q.correct_answer)

        return GeneratedQuestion(
            question=q.question,
            correct_answer=q.correct_answer,
            options=options,
            correct_index=correct_index,
            distractors=distractors,
            rationale=rationale,
            difficulty=q.difficulty,
        )
    except (ValidationError, ValueError, Exception) as exc:  # noqa: BLE001
        return GeneratedQuestion(
            question=q.question,
            correct_answer=q.correct_answer,
            options=[q.correct_answer],
            correct_index=0,
            distractors=[],
            rationale=[],
            difficulty=q.difficulty,
            error=f"{type(exc).__name__}: {exc}",
        )


async def generate_batch(
    client: AsyncAnthropic,
    settings: Settings,
    questions: list[QuestionInput],
) -> list[GeneratedQuestion]:
    """Generate distractors for many questions concurrently, order preserved.

    Concurrency is bounded by a semaphore so large batches don't trip API rate
    limits. Per-question failures are captured inside generate_one and never
    raise, so the returned list always lines up 1:1 with the input.
    """
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async def _bounded(q: QuestionInput) -> GeneratedQuestion:
        async with sem:
            return await generate_one(client, settings, q)

    return await asyncio.gather(*(_bounded(q) for q in questions))
