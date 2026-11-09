FROM python:3.12-slim
WORKDIR /srv
COPY --from=ghcr.io/astral-sh/uv:0.9.11 /uv /usr/local/bin/uv
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
ENV PATH="/srv/.venv/bin:$PATH" PYTHONUNBUFFERED=1
COPY backend/ ./
COPY warehouse/ /srv/warehouse/
COPY data/ /srv/data/
COPY scripts/verify_http.py /srv/verify_http.py
ENV WAREHOUSE_DIR=/srv/warehouse EVALUATION_DIR=/srv/data/evaluation
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
