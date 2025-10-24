.PHONY: check
check: lint test

.PHONY: lint
lint:
	uv run ruff format
	uv run ruff check --fix --show-fixes
	uv run mypy src/

.PHONY: test
test:
	uv run pytest --record-mode=new_episodes

.PHONY: unit-test
unit-test:
	uv run pytest -m "not integration"

.PHONY: integration-test
integration-test:
	uv run pytest -m "integration" --record-mode=new_episodes

