# Linting targets
lint-python:
	flake8 src/ test/

lint-format:
	black --check src/ test/

lint-pylint:
	pylint src/
	pylint test/

lint-sql:
	sqlfluff lint src/*.sql --ignore parsing --disable-progress-bar

lint-yaml:
	yamllint src

lint-markdown:
	markdownlint '**/*.md'

# Run all linting checks (stops on first failure, like CI)
lint: lint-python lint-format lint-pylint lint-sql lint-yaml lint-markdown