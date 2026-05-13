.PHONY: dev test lint build

dev:
	docker compose up --build

test:
	docker compose exec backend pytest

lint:
	docker compose exec backend ruff check .
	docker compose exec backend ruff format .

build:
	docker compose build
