FROM python:3.12-slim

WORKDIR /app

ARG APT_MIRROR=
ARG PIP_INDEX=https://pypi.org/simple
ARG UV_INDEX_URL=

RUN set -eux; \
    if [ -n "$APT_MIRROR" ]; then \
      if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
      fi; \
      if [ -f /etc/apt/sources.list ]; then \
        sed -i "s|deb.debian.org|${APT_MIRROR}|g; s|security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; \
      fi; \
    fi; \
    apt-get update && apt-get install -y --no-install-recommends \
      build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -i "$PIP_INDEX" uv

COPY pyproject.toml uv.lock .python-version README.md ./
COPY src ./src

RUN if [ -n "$UV_INDEX_URL" ]; then \
      sed -i \
        -e "s|https://pypi.org/simple|$UV_INDEX_URL|g" \
        -e "s|https://files.pythonhosted.org/packages|https://mirrors.aliyun.com/pypi/packages|g" \
        uv.lock; \
      UV_CONCURRENT_DOWNLOADS=2 UV_HTTP_TIMEOUT=120 \
        uv sync --frozen --no-dev --index-url "$UV_INDEX_URL"; \
    else \
      uv sync --frozen --no-dev; \
    fi

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src

RUN mkdir -p /app/data /app/workspace /app/skills

EXPOSE 8000
CMD ["uvicorn", "deepsupport_os.main:app", "--host", "0.0.0.0", "--port", "8000"]
