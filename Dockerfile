FROM ghcr.io/astral-sh/uv:0.5-python3.13-bookworm-slim

COPY [ "uv.lock", "pyproject.toml", "./" ]

RUN uv sync --locked --no-install-workspace --no-dev

# We don't want the tests
COPY src/songlinker ./src/songlinker

RUN uv sync --locked --no-editable --no-dev

ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION

ENTRYPOINT [ "tini", "--", "uv", "run", "python", "-m", "songlinker" ]
