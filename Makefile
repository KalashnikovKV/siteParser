.PHONY: up down logs test build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f app

test:
	.venv/bin/python -m pytest -q

build:
	cd web && npm run build
