.PHONY: coding_standards

coding_standards:
	poetry run black src/
	poetry run flake8 --exit-zero src/
	poetry run mypy src/
