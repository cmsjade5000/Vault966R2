ALEMBIC ?= alembic
ALEMBIC_FLAGS ?= -c alembic.ini
PYTHON ?= python3
RUFF ?= ruff
BLACK ?= black
PYTEST ?= pytest
DOCKER_COMPOSE ?= docker compose
POSTGRES_SERVICE ?= postgres
POSTGRES_USER ?= vault_user
POSTGRES_DB ?= vault966

.PHONY: db-upgrade db-downgrade db-reset lint test fmt db.up db.down db.migrate db.reset openapi

db-upgrade:
	$(ALEMBIC) $(ALEMBIC_FLAGS) upgrade head

db-downgrade:
	$(ALEMBIC) $(ALEMBIC_FLAGS) downgrade -1

db-reset:
	$(ALEMBIC) $(ALEMBIC_FLAGS) downgrade base
	$(ALEMBIC) $(ALEMBIC_FLAGS) upgrade head

db.up:
	$(DOCKER_COMPOSE) up -d $(POSTGRES_SERVICE)

db.down:
	$(DOCKER_COMPOSE) down -v

db.migrate:
	$(ALEMBIC) $(ALEMBIC_FLAGS) upgrade head

db.reset:
	$(DOCKER_COMPOSE) exec -T $(POSTGRES_SERVICE) psql -U $(POSTGRES_USER) -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$(POSTGRES_DB)' AND pid <> pg_backend_pid();"
	$(DOCKER_COMPOSE) exec -T $(POSTGRES_SERVICE) psql -U $(POSTGRES_USER) -d postgres -c "DROP DATABASE IF EXISTS $(POSTGRES_DB);"
	$(DOCKER_COMPOSE) exec -T $(POSTGRES_SERVICE) psql -U $(POSTGRES_USER) -d postgres -c "CREATE DATABASE $(POSTGRES_DB);"
	$(ALEMBIC) $(ALEMBIC_FLAGS) upgrade head

app.up:
	$(DOCKER_COMPOSE) up -d $(POSTGRES_SERVICE) api

app.down:
	$(DOCKER_COMPOSE) down

lint:
	$(RUFF) check .
	$(BLACK) --check .

fmt:
	$(BLACK) .
	$(RUFF) check . --fix

test:
	$(PYTEST)

openapi:
	$(PYTHON) scripts/generate_openapi.py
	$(PYTHON) scripts/generate_clients.py
