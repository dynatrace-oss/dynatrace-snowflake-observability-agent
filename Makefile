# Linting targets
lint-python:
	flake8 --config=.flake8 src/ test/

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
	markdownlint '**/*.md' --config .markdownlint.json

lint-bom:
	find src -name "bom.yml" -exec sh -c 'printf "%-50s " "$$1"; .venv/bin/check-jsonschema --schemafile test/src-bom.schema.json "$$1" || check-jsonschema --schemafile test/src-bom.schema.json "$$1"' _ {} \;

# Run all linting checks (stops on first failure, like CI)
lint: lint-python lint-format lint-pylint lint-sql lint-yaml lint-markdown lint-bom