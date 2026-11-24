FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.7.13 /uv /uvx /bin/
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY orders.py forecast.py common.py ./
ENV PATH="/app/.venv/bin:$PATH"
