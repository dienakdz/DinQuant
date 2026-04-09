.PHONY: install-backend-dev lint-backend format-backend check-backend check-backend-docker fix-backend fix-backend-docker install-frontend lint-frontend format-frontend check-frontend check-code format-code install-git-hooks run-pre-commit run-pre-commit-all

install-backend-dev:
	cd backend_api_python && python3 -m pip install -r requirements-dev.txt

lint-backend:
	cd backend_api_python && ruff check .

format-backend:
	cd backend_api_python && ruff format .

check-backend:
	cd backend_api_python && ruff format --check . && ruff check . && vulture app scripts run.py gunicorn_config.py

check-backend-docker:
	docker run --rm -v "$(PWD)/backend_api_python:/app" -w /app python:3.12-slim-bookworm sh -lc "pip install -q ruff vulture && ruff format --check . && ruff check . && vulture app scripts run.py gunicorn_config.py"

fix-backend:
	cd backend_api_python && ruff check . --fix && ruff format .

fix-backend-docker:
	docker run --rm -v "$(PWD)/backend_api_python:/app" -w /app python:3.12-slim-bookworm sh -lc "pip install -q ruff && ruff check . --fix && ruff format ."

install-frontend:
	cd frontend_vue && yarn install

lint-frontend:
	cd frontend_vue && yarn lint:check

format-frontend:
	cd frontend_vue && yarn format

check-frontend:
	cd frontend_vue && yarn format:check && yarn lint:check

check-code: check-backend check-frontend

format-code: format-backend format-frontend

install-git-hooks:
	pre-commit install

run-pre-commit:
	pre-commit run

run-pre-commit-all:
	pre-commit run -a
