"""FastAPI application entrypoint."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="MCQ Distractor Generator",
    description="Generates plausible-but-wrong answer choices for MCQs.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    """Liveness probe. Reports whether an API key is configured (without leaking it)."""
    return {
        "status": "ok",
        "model": settings.anthropic_model,
        "api_key_configured": settings.has_api_key,
    }
