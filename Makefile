.PHONY: coding_standards

coding_standards:
	poetry run black src/
	poetry run mypy src/
