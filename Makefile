.PHONY: check
check: lint test

.PHONY: lint
lint:
	poetry run black src/
	poetry run ruff check --fix --show-fixes src/
	poetry run mypy src/

.PHONY: test
test:
	poetry run pytest --record-mode=new_episodes src/

.PHONY: unit-test
unit-test:
	poetry run pytest -m "not integration" src/

.PHONY: integration-test
integration-test:
	poetry run pytest -m "integration" --record-mode=new_episodes src/

