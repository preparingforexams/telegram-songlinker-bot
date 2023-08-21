FROM python:3.11-slim

RUN useradd --system --create-home --home-dir /app -s /bin/bash app
USER app
ENV PATH=$PATH:/app/.local/bin

WORKDIR /app

ENV POETRY_VIRTUALENVS_CREATE=false

RUN pip install pipx==1.2.0 --user --no-cache
RUN pipx install poetry==1.6.1

COPY [ "poetry.toml", "poetry.lock", "pyproject.toml", "./" ]

# We don't want the tests
COPY src/songlinker ./src/songlinker

RUN poetry install --only main

ARG APP_VERSION
ENV BUILD_SHA=$APP_VERSION

ENTRYPOINT [ "poetry", "run", "python", "-m", "songlinker"  ]
