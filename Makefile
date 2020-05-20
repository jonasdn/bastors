.PHONY: test lint format

TESTS = $(wildcard tests/*.py)
MODULES = $(wildcard bastors/*.py)
PROGRAM = bastors.py

ALL_PY = $(TESTS) $(MODULES) $(PROGRAM)

test: $(TESTS)
	python3 -m unittest $^

lint: $(ALL_PY)
	flake8 $(ALL_PY)

format: $(ALL_PY)
	black $(ALL_PY)
