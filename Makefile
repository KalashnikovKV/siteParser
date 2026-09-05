.PHONY: up down logs test build scrape

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f app

scrape:
	docker compose --profile scrape run --rm scrape

test:
	.venv/bin/python -m pytest -q

build:
	cd web && npm run build
