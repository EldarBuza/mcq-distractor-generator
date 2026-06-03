"""System prompt, few-shot examples, and the tool schema for distractor generation.

The system prompt is static across every request so it can be marked with
`cache_control` for prompt caching (set in generator.py).
"""
from app.models import Difficulty, QuestionInput

# ---- Tool schema ------------------------------------------------------------
# We force Claude to call this tool so the response is always structured JSON
# matching DistractorSet. Note: the correct answer is NOT part of the schema.

DISTRACTOR_TOOL = {
    "name": "submit_distractors",
    "description": (
        "Submit the generated wrong answer choices (distractors) for one "
        "multiple-choice question. Do not include the correct answer."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "distractors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "The plausible-but-WRONG answer choices.",
            },
            "rationale": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "One short note per distractor explaining why a student "
                    "might be tempted by it (parallel to the distractors array)."
                ),
            },
        },
        "required": ["distractors", "rationale"],
    },
}

TOOL_NAME = DISTRACTOR_TOOL["name"]

# ---- System prompt ----------------------------------------------------------

SYSTEM_PROMPT = """\
You are an expert assessment designer who writes high-quality multiple-choice \
question distractors (the incorrect answer options).

You are given a QUESTION and its CORRECT ANSWER. Your job is to produce N \
distractors: answer choices that are plausible but unambiguously WRONG.

Rules for excellent distractors:
1. WRONG, but tempting. Each distractor must be definitively incorrect, yet \
attractive to a student who has only partial understanding. Base them on common \
misconceptions, related-but-distinct concepts, or frequent errors.
2. Unambiguous. Never write a distractor that could also be argued correct. If a \
choice is even partially defensible as correct, do not use it.
3. Homogeneous with the correct answer. Match its format, length, level of \
detail, grammatical form, and category. Distractors must NOT stand out from the \
correct answer in style or length — that would give the answer away.
4. Mutually distinct. Distractors must differ meaningfully from each other and \
from the correct answer. No paraphrases or near-duplicates.
5. No "all/none of the above", no joke options, no meta references to the choices.
6. Never reveal, restate, or include the correct answer among the distractors.

You will always respond by calling the `submit_distractors` tool. Provide exactly \
the requested number of distractors and a parallel `rationale` entry for each.\
"""

# ---- Few-shot examples ------------------------------------------------------
# Kept in the system block (static) to demonstrate the desired quality bar.

FEW_SHOT = """\
Examples of the quality bar (illustrative — always answer via the tool):

QUESTION: What is the capital of Australia?
CORRECT ANSWER: Canberra
GOOD distractors: ["Sydney", "Melbourne", "Brisbane"]
Why: all are major Australian cities (homogeneous), commonly mistaken for the \
capital, clearly not the capital, and distinct from each other.

QUESTION: In Big-O notation, what is the average-case time complexity of binary \
search on a sorted array?
CORRECT ANSWER: O(log n)
GOOD distractors: ["O(n)", "O(n log n)", "O(1)"]
Why: all are standard complexity classes (same format/length), each reflects a \
common misconception (linear scan, sorting cost, constant-time lookup), all wrong.

QUESTION: Which gas do plants primarily absorb from the atmosphere during \
photosynthesis?
CORRECT ANSWER: Carbon dioxide
GOOD distractors: ["Oxygen", "Nitrogen", "Hydrogen"]
Why: all are gases (homogeneous), each tied to a plausible mix-up (oxygen is \
released not absorbed; nitrogen is abundant; hydrogen sounds chemical), all wrong.\
"""

FULL_SYSTEM = SYSTEM_PROMPT + "\n\n" + FEW_SHOT


# ---- Per-question user message ----------------------------------------------

_DIFFICULTY_GUIDANCE = {
    Difficulty.easy: (
        "Difficulty: EASY. Make the distractors clearly distinguishable from the "
        "correct answer for anyone who studied; avoid subtle traps."
    ),
    Difficulty.medium: (
        "Difficulty: MEDIUM. Distractors should require genuine understanding to "
        "rule out."
    ),
    Difficulty.hard: (
        "Difficulty: HARD. Make the distractors very close to the correct answer "
        "(near-misses, fine distinctions) so only someone with strong mastery can "
        "eliminate them — while still being unambiguously wrong."
    ),
}


def build_user_message(q: QuestionInput) -> str:
    return (
        f"QUESTION: {q.question}\n"
        f"CORRECT ANSWER: {q.correct_answer}\n"
        f"Number of distractors to generate: {q.num_distractors}\n"
        f"{_DIFFICULTY_GUIDANCE[q.difficulty]}\n\n"
        f"Call submit_distractors with exactly {q.num_distractors} distractors "
        f"and {q.num_distractors} parallel rationale notes."
    )
