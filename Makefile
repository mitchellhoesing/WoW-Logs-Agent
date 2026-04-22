.PHONY: install test lint type fmt check run

install:
	pip install -e '.[dev]'
	pre-commit install || true

test:
	pytest -q

lint:
	ruff check src tests

fmt:
	ruff format src tests
	ruff check --fix src tests

type:
	mypy src

check: lint type test

run:
	wowlogs-agent --help
