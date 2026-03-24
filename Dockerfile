FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system --no-cache .

FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home --shell /bin/bash forge

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

COPY --chown=forge:forge src/ ./src/
COPY --chown=forge:forge alembic/ ./alembic/
COPY --chown=forge:forge alembic.ini .
COPY --chown=forge:forge pyproject.toml .

USER forge

EXPOSE 8000

CMD ["uvicorn", "forge.main:app", "--host", "0.0.0.0", "--port", "8000"]
