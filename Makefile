.PHONY: install format lint typecheck test check build

install:
	python -m pip install -e ".[dev]"

format:
	ruff format .
	ruff check --fix .

lint:
	ruff format --check .
	ruff check .

typecheck:
	mypy src tests

test:
	pytest

check: lint typecheck test

build:
	python -m build
