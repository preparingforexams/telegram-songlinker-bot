.PHONY: check
check: lint test

.PHONY: lint
lint:
	uv run ruff format src/
	uv run ruff check --fix --show-fixes src/
	uv run mypy src/

.PHONY: test
test:
	uv run pytest --record-mode=new_episodes src/

.PHONY: unit-test
unit-test:
	uv run pytest -m "not integration" src/

.PHONY: integration-test
integration-test:
	uv run pytest -m "integration" --record-mode=new_episodes src/

