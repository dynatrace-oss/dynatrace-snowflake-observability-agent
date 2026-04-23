# Copyright (c) 2025 Dynatrace Open Source
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

.PHONY: lint lint-python lint-format lint-pylint lint-sql lint-yaml lint-markdown lint-bom lint-shell build docs package test test-documentation test-bash test-bash-slow test-core test-plugins docker-build docker-clean docker-test

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
	markdownlint-cli2 '[^.]*/**/*.md' '*.md' --config .markdownlint.json

lint-bom:
	find src -name "bom.yml" -exec sh -c 'printf "%-50s " "$$1"; .venv/bin/check-jsonschema --schemafile test/src-bom.schema.json "$$1" || check-jsonschema --schemafile test/src-bom.schema.json "$$1"' _ {} \;

lint-shell:
	shellcheck --severity=warning scripts/deploy/*.sh scripts/dev/*.sh scripts/test/*.sh test/bash/*.bats

# Run all linting checks (stops on first failure, like CI)
lint: lint-python lint-format lint-pylint lint-sql lint-yaml lint-markdown lint-bom lint-shell

build:
	./scripts/dev/build.sh

docs:
	./scripts/dev/build_docs.sh

package:
	./scripts/dev/package.sh

# Testing targets
test-documentation:
	.venv/bin/pytest test/core/test_documentation.py -k "TestDocumentation"

test-bash:
	.venv/bin/pytest test/core/test_bash_scripts.py -v

test-bash-slow:
	.venv/bin/pytest test/core/test_bash_scripts.py -v --run-slow

test-core:
	.venv/bin/pytest test/core/test_config.py -k "TestConfig"
	.venv/bin/pytest test/core/test_util.py -k "TestUtil"
	.venv/bin/pytest test/core/test_views_structure.py -k "TestViews"
	.venv/bin/pytest test/core/test_connector.py -k "TestTelemetrySender"
	.venv/bin/pytest test/otel/test_events.py -k "TestEvents"
	.venv/bin/pytest test/otel/test_otel_manager.py -k "TestOtelManager"

test-plugins:
	.venv/bin/pytest test/plugins/

# Run all tests (mirrors CI test jobs, excludes slow bash tests)
test: test-documentation test-bash test-core test-plugins

DOCKER_TAG ?= dsoa-deploy:local

docker-build: ## Build DSOA deployment Docker image (run build.sh first)
	@if [ ! -d "build" ] || [ -z "$$(ls -A build 2>/dev/null)" ]; then \
		echo "WARNING: build/ directory is missing or empty. Run ./scripts/dev/build.sh first."; \
	fi
	docker build -t $(DOCKER_TAG) .

docker-clean: ## Remove DSOA Docker image and dangling layers
	docker rmi $(DOCKER_TAG) 2>/dev/null || true
	docker image prune -f
