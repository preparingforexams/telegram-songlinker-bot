.PHONY: nice

nice:
	poetry run black src/
	poetry run mypy src/
