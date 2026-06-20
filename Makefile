include Makefile.txt

# ---- README ALIASES ----
.PHONY: app.up app.down db.up db.down db.migrate db.reset fmt lint test openapi vault.audit codex.status codex.check codex.full codex.live codex.skills

app.up: up ## Start API + Postgres (Docker)

app.down: down ## Stop API + Postgres (Docker)

db.up: ## Start Postgres only (Docker)
	docker compose up -d postgres

db.down: ## Stop Postgres only (Docker)
	docker compose stop postgres

db.migrate: migrate ## Apply Alembic migrations (Docker)

db.reset: ## Drop/recreate POSTGRES_DB then migrate (confirm)
	@read -p "Drop and recreate $${POSTGRES_DB:-vault966} inside the Postgres container? (y/N) " ans; \
	if [ "$$ans" = "y" ]; then \
		docker compose exec -T postgres psql -U "$${POSTGRES_USER:-vault_user}" -d postgres -c "DROP DATABASE IF EXISTS \\\"$${POSTGRES_DB:-vault966}\\\";"; \
		docker compose exec -T postgres psql -U "$${POSTGRES_USER:-vault_user}" -d postgres -c "CREATE DATABASE \\\"$${POSTGRES_DB:-vault966}\\\";"; \
		$(MAKE) db.migrate; \
	else echo "Cancelled."; fi

fmt: ## Format Python (Black + Ruff) and JS (Prettier)
	python3 -m black .
	python3 -m ruff check --fix .
	npm run fmt

lint: ## Lint Python (Ruff) and JS (Prettier)
	python3 -m ruff check .
	python3 -m black --check .
	npm run lint

test: ## Run pytest
	python3 -m pytest

vault.audit: ## Check structural integrity and imported-source drift
	python3 scripts/audit_vault_integrity.py

openapi: ## Freeze OpenAPI + regenerate clients
	python3 scripts/generate_openapi.py
	python3 scripts/generate_clients.py

codex.status: ## Show git state, repo skill links, and live service status
	scripts/codex_check.sh status

codex.check: ## Run the default Codex verification suite
	scripts/codex_check.sh quick

codex.full: ## Run full lint and test checks for Codex completion
	scripts/codex_check.sh full

codex.live: ## Restart and verify the deployed macOS service
	scripts/codex_check.sh live

codex.skills: ## List repo-scoped Codex skill links
	scripts/codex_check.sh skills
