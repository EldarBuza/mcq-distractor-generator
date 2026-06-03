"""Manual smoke test against the real Anthropic API.

Run from the backend/ directory (with .venv active and .env containing your key):

    .venv\\Scripts\\python.exe scripts\\smoke_generate.py

It generates distractors for a couple of sample questions and prints them,
verifying the correct answer is present exactly once and unaltered.
"""
import asyncio
import sys
from pathlib import Path

# Windows consoles default to cp1252; model output may contain Unicode
# (subscripts, math symbols). Force UTF-8 so printing never crashes.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Make `app` importable when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from anthropic import AsyncAnthropic  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.generator import generate_one  # noqa: E402
from app.models import Difficulty, QuestionInput  # noqa: E402

SAMPLES = [
    QuestionInput(question="What is the capital of Australia?",
                  correct_answer="Canberra", num_distractors=3,
                  difficulty=Difficulty.medium),
    QuestionInput(question="What is the time complexity of binary search?",
                  correct_answer="O(log n)", num_distractors=3,
                  difficulty=Difficulty.hard),
]


async def main() -> int:
    settings = get_settings()
    if not settings.has_api_key:
        print("ERROR: no ANTHROPIC_API_KEY found. Create backend/.env first.")
        return 1

    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    print(f"Model: {settings.anthropic_model}\n")

    for q in SAMPLES:
        r = await generate_one(client, settings, q)
        print(f"Q: {r.question}  [{r.difficulty.value}]")
        if r.error:
            print(f"  ERROR: {r.error}\n")
            continue
        for i, opt in enumerate(r.options):
            mark = "  <-- correct" if i == r.correct_index else ""
            print(f"  {chr(65 + i)}. {opt}{mark}")
        # Invariants.
        assert r.options.count(r.correct_answer) == 1, "answer not present exactly once"
        assert r.options[r.correct_index] == r.correct_answer
        print()

    print("OK: correct answer preserved exactly once in every question.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
