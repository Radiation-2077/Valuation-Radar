.PHONY: setup migrate import-legacy dev build test test-e2e lint typecheck

setup:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/pip install -e "apps/api[dev]"
	pnpm install
	mkdir -p storage/artifacts storage/backups storage/logs storage/staging
	$(MAKE) migrate
	$(MAKE) import-legacy

migrate:
	pnpm db:migrate

import-legacy:
	PYTHONPATH=apps/api .venv/bin/python -m app.cli import-legacy --data-dir ../data --reports-dir ..

dev:
	pnpm dev

build:
	pnpm build

typecheck:
	pnpm typecheck

lint:
	pnpm lint

test:
	PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pnpm test

test-e2e:
	pnpm test:e2e
