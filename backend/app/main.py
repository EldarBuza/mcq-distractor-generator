"""FastAPI application entrypoint."""
from contextlib import asynccontextmanager

from anthropic import AsyncAnthropic
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.generator import generate_batch
from app.models import GenerateRequest, GenerateResponse
from app.parsing import ParseResult, parse_text, parse_upload
from pydantic import BaseModel, Field

# Reject uploads larger than this to avoid unbounded memory use.
MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create one shared Anthropic client for the app's lifetime."""
    app.state.anthropic = (
        AsyncAnthropic(api_key=settings.anthropic_api_key)
        if settings.has_api_key
        else None
    )
    yield
    if app.state.anthropic is not None:
        await app.state.anthropic.close()


app = FastAPI(
    title="MCQ Distractor Generator",
    description="Generates plausible-but-wrong answer choices for MCQs.",
    version="0.1.0",
    lifespan=lifespan,
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


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest) -> GenerateResponse:
    """Generate distractors for a batch of questions."""
    client = app.state.anthropic
    if client is None:
        raise HTTPException(
            status_code=503,
            detail="ANTHROPIC_API_KEY is not configured on the server.",
        )
    results = await generate_batch(
        client, settings, req.questions, verify=req.verify
    )
    return GenerateResponse(results=results)


class ParseTextRequest(BaseModel):
    text: str = Field(..., max_length=1_000_000)
    format: str = "auto"  # auto | csv | json | lines


@app.post("/parse-text", response_model=ParseResult)
async def parse_text_endpoint(req: ParseTextRequest) -> ParseResult:
    """Parse a raw text blob (pasted input) into questions for preview."""
    return parse_text(req.text, req.format)


@app.post("/parse", response_model=ParseResult)
async def parse(file: UploadFile = File(...)) -> ParseResult:
    """Parse an uploaded CSV/JSON/TSV/TXT file into questions for preview.

    Does not call the LLM — returns the parsed questions and any per-row errors
    so the frontend can show the user what was understood before generating.
    """
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (limit {MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )
    return parse_upload(file.filename or "", content)
