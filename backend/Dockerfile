FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock .python-version README.md ./
COPY src ./src

RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src

RUN mkdir -p /app/data /app/workspace /app/skills

EXPOSE 8000
CMD ["uvicorn", "deepsupport_os.main:app", "--host", "0.0.0.0", "--port", "8000"]
