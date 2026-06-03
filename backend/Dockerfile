# Backend image: FastAPI served by uvicorn.
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install deps first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App code.
COPY app ./app

EXPOSE 8000

# The API key is provided at runtime via compose env_file (not baked in).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
