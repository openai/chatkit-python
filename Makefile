.PHONY: sync install format format-check lint mypy pyright test build serve-docs deploy-docs check

UV_ENV := env -i PATH="$(PATH)" HOME="$(HOME)"
UV := $(UV_ENV) uv --no-config
UV_LOCK_ARGS := --locked --default-index https://pypi.org/simple

sync:
	$(UV) sync $(UV_LOCK_ARGS) --all-extras --all-packages --group dev

install: sync

format:
	$(UV) run $(UV_LOCK_ARGS) ruff format
	$(UV) run $(UV_LOCK_ARGS) ruff check --fix

format-check:
	$(UV) run $(UV_LOCK_ARGS) ruff format --check

lint:
	$(UV) run $(UV_LOCK_ARGS) ruff check

mypy:
	$(UV) run $(UV_LOCK_ARGS) mypy .

pyright:
	$(UV) run $(UV_LOCK_ARGS) pyright

test:
	$(UV_ENV) PYTHONPATH=. uv --no-config run $(UV_LOCK_ARGS) pytest

build:
	$(UV) build --default-index https://pypi.org/simple

serve-docs:
	$(UV) run $(UV_LOCK_ARGS) mkdocs serve

deploy-docs:
	$(UV) run $(UV_LOCK_ARGS) mkdocs gh-deploy --force --verbose

check: format-check lint pyright test
