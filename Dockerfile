FROM python:3.11-slim

WORKDIR /app

RUN pip install poetry==1.3.2 --no-cache
RUN poetry config virtualenvs.create false

COPY [ "poetry.toml", "poetry.lock", "pyproject.toml", "./" ]

RUN poetry install --no-dev

COPY src .

ARG build
ENV BUILD_SHA=$build

ENTRYPOINT [ "python", "-m", "songlinker" ]
