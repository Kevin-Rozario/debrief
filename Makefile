.PHONY: setup seed api web test

ifeq ($(OS),Windows_NT)
SYS_PYTHON := python
PYTHON := backend/.venv/Scripts/python.exe
else
SYS_PYTHON := python3
PYTHON := backend/.venv/bin/python
endif

setup:
	$(SYS_PYTHON) -m venv backend/.venv
	$(abspath $(PYTHON)) -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt

seed:
	cd backend && $(abspath $(PYTHON)) -m app.seed

api:
	cd backend && $(abspath $(PYTHON)) -m uvicorn app.main:app --host 127.0.0.1 --port 4000 --reload

web:
	@echo "The screen is not built yet."
	@exit 1

test:
	cd backend && $(abspath $(PYTHON)) -m pytest
