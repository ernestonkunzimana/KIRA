# Makefile for building and running production services
.PHONY: build prod-up prod-down prod-logs ci

build:
	docker compose -f docker-compose.prod.yml build --parallel

prod-up:
	docker compose -f docker-compose.prod.yml up -d --remove-orphans

prod-down:
	docker compose -f docker-compose.prod.yml down

prod-logs:
	docker compose -f docker-compose.prod.yml logs -f

ci:
	@echo "Run CI lint and tests locally"
	./.venv/bin/pytest -q
	./.venv/bin/flake8 || true
