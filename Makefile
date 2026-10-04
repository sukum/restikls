SRC_DIR := src
TEST_DIR := tests

.DEFAULT_GOAL := help
help:
	@echo "Available targets:"
	@echo "  test         - Run tests"
	@echo "  format-check - Check code formatting"
	@echo "  format-fix   - Fix code formatting"
	@echo "  lint-check   - Run linter (ruff)"
	@echo "  lint-fix     - Fix code linting (ruff)"
	@echo "  type-check   - Run type check (ty)"
	@echo "  ..."

.PHONY: test format-check format-diff format-fix lint-check lint-diff lint-fix type-check

test:
	uv run pytest $(TEST_DIR)

format-check:
	uvx ruff format --check $(SRC_DIR)
	uvx ruff check --select I -e $(SRC_DIR)

format-diff:
	uvx ruff format --diff $(SRC_DIR)
	uvx ruff check --select I --diff -e $(SRC_DIR)

format-fix:
	uvx ruff format $(SRC_DIR)
	uvx ruff check --select I --fix $(SRC_DIR)

lint-check:
	uvx ruff check -e $(SRC_DIR)

lint-diff:
	uvx ruff check --diff -e $(SRC_DIR)

lint-fix:
	uvx ruff check --fix $(SRC_DIR)

type-check:
	uvx ty check $(SRC_DIR)

css:
	npx tailwindcss -i ./src/restikls/static/css/input.css -o ./src/restikls/static/css/style.css --minify
