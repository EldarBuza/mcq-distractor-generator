"""Generate question + correct-answer pairs from a block of source text.

This is the front half of the pipeline: it only drafts (question, answer) pairs.
The user then reviews/edits them and runs the normal distractor generation.
"""
from anthropic import AsyncAnthropic
from pydantic import ValidationError

from app.config import Settings
from app.generator import _extract_tool_input, _norm
from app.models import Difficulty, QuestionDraftSet, QuestionInput
from app.prompts import (
    QUESTIONS_SYSTEM,
    QUESTIONS_TOOL,
    QUESTIONS_TOOL_NAME,
    build_questions_message,
)

# Drafting several questions needs more room than a single distractor set.
MAX_TOKENS = 2048


async def generate_questions(
    client: AsyncAnthropic,
    settings: Settings,
    text: str,
    count: int,
    difficulty: Difficulty,
) -> list[QuestionInput]:
    """Draft up to `count` question + answer pairs from `text`.

    Pairs that are blank, duplicate (by question), or fail validation (e.g. too
    long) are dropped rather than raising, so a single bad item never sinks the
    whole batch.
    """
    message = await client.messages.create(
        model=settings.anthropic_model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": QUESTIONS_SYSTEM,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        tools=[QUESTIONS_TOOL],
        tool_choice={"type": "tool", "name": QUESTIONS_TOOL_NAME},
        messages=[
            {
                "role": "user",
                "content": build_questions_message(text, count, difficulty),
            }
        ],
    )
    draft = _extract_tool_input(message, QUESTIONS_TOOL_NAME, QuestionDraftSet)

    out: list[QuestionInput] = []
    seen: set[str] = set()
    for item in draft.questions:
        question = item.question.strip()
        answer = item.answer.strip()
        if not question or not answer:
            continue
        key = _norm(question)
        if key in seen:
            continue
        try:
            out.append(
                QuestionInput(
                    question=question,
                    correct_answer=answer,
                    num_distractors=3,
                    difficulty=difficulty,
                )
            )
        except ValidationError:
            continue  # e.g. exceeds length limits — skip this draft
        seen.add(key)
        if len(out) >= count:
            break
    return out
