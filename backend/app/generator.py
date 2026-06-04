"""Core distractor generation: call Claude, validate, assemble, shuffle.

The correct answer is added to the option list HERE, in code — never by the
model — so the user's answer is guaranteed to survive verbatim.
"""
import asyncio
import random

from anthropic import AsyncAnthropic
from pydantic import ValidationError

from app.config import Settings
from app.models import (
    DistractorSet,
    GeneratedQuestion,
    QuestionInput,
    ReviewResult,
)
from app.prompts import (
    DISTRACTOR_TOOL,
    FULL_SYSTEM,
    REVIEW_SYSTEM,
    REVIEW_TOOL,
    REVIEW_TOOL_NAME,
    TOOL_NAME,
    build_review_message,
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


def _extract_tool_input(message, tool_name, model_cls):
    """Pull the input of the named tool_use block and validate it against model_cls."""
    for block in message.content:
        if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
            return model_cls.model_validate(block.input)
    raise ValueError(f"model did not call the {tool_name} tool")


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
    return _extract_tool_input(message, TOOL_NAME, DistractorSet)


async def _review_model(
    client: AsyncAnthropic,
    settings: Settings,
    q: QuestionInput,
    distractors: list[str],
) -> ReviewResult:
    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": REVIEW_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[REVIEW_TOOL],
        tool_choice={"type": "tool", "name": REVIEW_TOOL_NAME},
        messages=[{"role": "user", "content": build_review_message(q, distractors)}],
    )
    return _extract_tool_input(message, REVIEW_TOOL_NAME, ReviewResult)


async def _verify_distractors(
    client: AsyncAnthropic,
    settings: Settings,
    q: QuestionInput,
    distractors: list[str],
    rationale: list[str],
) -> tuple[list[str], list[str]]:
    """Run the review pass; keep only distractors judged ok, filtering rationale
    in lockstep. Missing/short verdicts default to KEEP, so a malformed review
    never silently empties an otherwise-good set."""
    review = await _review_model(client, settings, q, distractors)
    kept_d: list[str] = []
    kept_r: list[str] = []
    for i, d in enumerate(distractors):
        verdict = review.verdicts[i] if i < len(review.verdicts) else None
        if verdict is None or verdict.ok:
            kept_d.append(d)
            kept_r.append(rationale[i] if i < len(rationale) else "")
    return kept_d, kept_r


async def _replenish_verified(
    client: AsyncAnthropic,
    settings: Settings,
    q: QuestionInput,
    distractors: list[str],
    rationale: list[str],
) -> tuple[list[str], list[str]]:
    """One attempt to top up a verified set that fell short: generate fresh
    candidates, drop ones we already kept, verify them, and append the keepers
    up to the requested count."""
    need = q.num_distractors - len(distractors)
    have = {_norm(d) for d in distractors}
    fresh = await _call_model(client, settings, q)
    candidates = [
        d
        for d in _clean_distractors(
            fresh.distractors, q.correct_answer, q.num_distractors
        )
        if _norm(d) not in have
    ][:need]
    if not candidates:
        return distractors, rationale
    new_d, new_r = await _verify_distractors(
        client, settings, q, candidates, fresh.rationale[: len(candidates)]
    )
    return distractors + new_d, rationale + new_r


async def generate_one(
    client: AsyncAnthropic,
    settings: Settings,
    q: QuestionInput,
    verify: bool = False,
) -> GeneratedQuestion:
    """Generate distractors for one question and return a finished MCQ.

    When ``verify`` is True, a second LLM pass critiques the distractors and
    drops any judged ambiguous, defensible-as-correct, or duplicate.

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

        # Optional second pass: critique and drop weak distractors, then top up
        # once if verification left us short of the requested count.
        if verify:
            distractors, rationale = await _verify_distractors(
                client, settings, q, distractors, rationale
            )
            if 0 < len(distractors) < q.num_distractors:
                distractors, rationale = await _replenish_verified(
                    client, settings, q, distractors, rationale
                )
            if not distractors:
                raise ValueError("no distractors survived verification")

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
            verified=verify,
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
    verify: bool = False,
) -> list[GeneratedQuestion]:
    """Generate distractors for many questions concurrently, order preserved.

    Concurrency is bounded by a semaphore so large batches don't trip API rate
    limits. Per-question failures are captured inside generate_one and never
    raise, so the returned list always lines up 1:1 with the input.
    """
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async def _bounded(q: QuestionInput) -> GeneratedQuestion:
        async with sem:
            return await generate_one(client, settings, q, verify=verify)

    return await asyncio.gather(*(_bounded(q) for q in questions))
