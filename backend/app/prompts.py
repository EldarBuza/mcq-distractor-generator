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

# ---- Review tool schema -----------------------------------------------------
# Used by the optional verification pass. The reviewer judges each candidate
# distractor and returns a parallel array of verdicts.

REVIEW_TOOL = {
    "name": "submit_review",
    "description": (
        "Submit a verdict for each candidate distractor of one multiple-choice "
        "question, in the same order they were given."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "verdicts": {
                "type": "array",
                "description": (
                    "One verdict per candidate distractor, parallel to the "
                    "numbered list provided."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "ok": {
                            "type": "boolean",
                            "description": (
                                "True if the distractor is a good, "
                                "unambiguously-wrong option; false if it should "
                                "be dropped."
                            ),
                        },
                        "issue": {
                            "type": "string",
                            "description": (
                                "If ok is false, a short reason (e.g. "
                                "'could be argued correct', 'near-duplicate of "
                                "the answer'). Empty when ok is true."
                            ),
                        },
                    },
                    "required": ["ok", "issue"],
                },
            }
        },
        "required": ["verdicts"],
    },
}

REVIEW_TOOL_NAME = REVIEW_TOOL["name"]

# ---- Answer-check tool schema -----------------------------------------------
# Used by the optional, advisory answer sanity-check. The model judges whether
# the user's supplied correct answer is actually correct for the question.

CHECK_TOOL = {
    "name": "submit_answer_check",
    "description": (
        "Report whether the provided answer is actually correct for the "
        "question."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "ok": {
                "type": "boolean",
                "description": (
                    "True if the provided answer is correct (or clearly "
                    "acceptable) for the question; false if it appears wrong."
                ),
            },
            "note": {
                "type": "string",
                "description": (
                    "If ok is false, a brief explanation of why the answer "
                    "looks incorrect and what the correct answer likely is. "
                    "Keep it to one or two sentences. Empty or brief when ok."
                ),
            },
        },
        "required": ["ok", "note"],
    },
}

CHECK_TOOL_NAME = CHECK_TOOL["name"]

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

# ---- Review system prompt ---------------------------------------------------
# Static across requests, so it is cache-able like FULL_SYSTEM.

REVIEW_SYSTEM = """\
You are a strict reviewer of multiple-choice question distractors (the incorrect \
answer options). You are given a QUESTION, its CORRECT ANSWER, and a numbered \
list of CANDIDATE distractors. Judge each candidate independently.

Reject a candidate (ok = false) if ANY of these is true:
1. It could be argued to be correct, or is partially defensible as an answer — \
a distractor must be unambiguously WRONG.
2. It is a paraphrase, synonym, or near-duplicate of the correct answer.
3. It is a paraphrase or near-duplicate of another candidate distractor.
4. It is not homogeneous with the correct answer (wildly different format, \
length, or category, so it gives the answer away).
5. It is nonsensical, a joke, "all/none of the above", or references the choices.

Otherwise accept it (ok = true). Be conservative: when a candidate is clearly \
fine, keep it. Only reject candidates that genuinely violate a rule. Always \
respond by calling the `submit_review` tool with exactly one verdict per \
candidate, in order.\
"""

# ---- Answer-check system prompt ---------------------------------------------
# Static across requests, so it is cache-able like the others.

ANSWER_CHECK_SYSTEM = """\
You are a meticulous fact-checker for multiple-choice questions. You are given a \
QUESTION and a PROVIDED ANSWER. Decide whether the provided answer is actually \
correct for the question.

- ok = true if the provided answer is correct, or is one clearly acceptable \
answer among several valid ones.
- ok = false if the provided answer is factually wrong, does not answer the \
question, or is a common misconception. In that case, the `note` should briefly \
say why and state the correct answer.

Be careful and avoid false alarms: only mark ok = false when you are confident \
the answer is wrong. If the question is subjective, ambiguous, or depends on \
context you cannot see, prefer ok = true. You are advising the author — you must \
NOT rewrite the question or answer. Always respond by calling the \
`submit_answer_check` tool.\
"""


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


def build_review_message(q: QuestionInput, distractors: list[str]) -> str:
    numbered = "\n".join(f"{i + 1}. {d}" for i, d in enumerate(distractors))
    return (
        f"QUESTION: {q.question}\n"
        f"CORRECT ANSWER: {q.correct_answer}\n\n"
        f"CANDIDATE distractors:\n{numbered}\n\n"
        f"Call submit_review with exactly {len(distractors)} verdicts, one per "
        f"candidate, in the same order."
    )


def build_answer_check_message(q: QuestionInput) -> str:
    return (
        f"QUESTION: {q.question}\n"
        f"PROVIDED ANSWER: {q.correct_answer}\n\n"
        "Call submit_answer_check with your verdict."
    )


def build_regen_message(
    q: QuestionInput, count: int, avoid: list[str]
) -> str:
    """Ask for `count` fresh distractors that avoid an existing set — used when
    regenerating only the unlocked distractors of a question."""
    avoid_block = ""
    if avoid:
        listed = "\n".join(f"- {a}" for a in avoid)
        avoid_block = (
            "\nThese options already exist for this question. Do NOT repeat, "
            f"paraphrase, or closely resemble any of them:\n{listed}\n"
        )
    return (
        f"QUESTION: {q.question}\n"
        f"CORRECT ANSWER: {q.correct_answer}\n"
        f"Number of distractors to generate: {count}\n"
        f"{_DIFFICULTY_GUIDANCE[q.difficulty]}\n"
        f"{avoid_block}\n"
        f"Call submit_distractors with exactly {count} distractors "
        f"and {count} parallel rationale notes."
    )
