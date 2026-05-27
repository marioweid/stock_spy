FROM python:3.13-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first so this layer is cached across code changes.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

# Install the project itself (shared core + the signal monitor + the swing scanner).
COPY spy_core ./spy_core
COPY signal_spy ./signal_spy
COPY swing_spy ./swing_spy
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

# config files and the data/ volume are mounted at runtime; compose sets each service's command.
CMD ["python", "-m", "signal_spy", "monitor"]
