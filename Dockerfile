FROM ghcr.io/blindfoldedsurgery/poetry:1.1.1-pipx-3.11-bookworm

COPY [ "poetry.toml", "poetry.lock", "pyproject.toml", "./" ]

RUN poetry install --no-interaction --ansi --only=main --no-root

# We don't want the tests
COPY src/songlinker ./src/songlinker

RUN poetry install --no-interaction --ansi --only-root

ARG APP_VERSION
ENV APP_VERSION=$APP_VERSION

ENTRYPOINT [ "tini", "--", "poetry", "run", "python", "-m", "songlinker" ]
