.PHONY: up down logs test build scrape lock audit

LOCK = uv pip compile pyproject.toml --universal --python-version 3.12 --generate-hashes

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

# После правки зависимостей в pyproject.toml: пересобрать lock-файлы с хэшами.
lock:
	$(LOCK) -o requirements.txt
	$(LOCK) --extra dev -o requirements-dev.txt

audit:
	uvx pip-audit --disable-pip --require-hashes -r requirements-dev.txt
	cd web && npm audit --audit-level=moderate
