<p align="center">
  <a href="../runbook.md">简体中文</a>
  &nbsp;|&nbsp;
  <a href="./runbook.md"><strong>English</strong></a>
</p>

# Operations Runbook

This document covers local development startup, health checks, and common failures. See [Quick Start](QUICKSTART.md) for first-time installation, [Dependencies](DEPENDENCIES.md) for version details, and [Codex Skill setup](CODEX_SKILLS.md) for Skill installation.

> **Scope:** The project is currently developed and validated primarily for the A-share market and Linux. The commands below primarily target Linux. The AI valuation logic itself is not market-specific, but non-A-share markets and non-Linux environments have not been tested; verify commands such as `date` and SQLite backups for your shell and platform, and use other configurations at your own risk. The project follows a long-term value-investing approach: buy good companies at reasonable or cheap prices and hold them for the long term; it is not intended for short-term speculation.

## Start

Start all development processes from the repository root:

```bash
pnpm dev
```

If dependencies or the database have not been initialized:

```bash
pnpm run bootstrap
pnpm dev
```

To inspect individual process logs, start them separately:

```bash
pnpm dev:api
pnpm dev:web
pnpm dev:worker
pnpm dev:scheduler
```

## Check status

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/schedule
curl -s http://127.0.0.1:8000/api/v1/jobs
curl -s http://127.0.0.1:8000/api/v1/reviews
```

The web development address is <http://127.0.0.1:5173>, and the API documentation is at <http://127.0.0.1:8000/docs>.

## Refresh market data manually

Select **Refresh quotes now** in the web application's **Update Center**, or call:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: manual-$(date +%s)" \
  -d '{"job_type":"market_refresh","scope":"all"}'
```

Refresh jobs require the worker. When only `pnpm dev:web` is running, jobs remain queued.

## Re-value with Codex

Select **Request Codex re-valuation** in the valuation details. When the job completes, the candidate version appears under **Update Center → Codex valuations awaiting review**.

Check the CLI, login state, and Skills:

```bash
codex --version
codex login status
test -f "$HOME/.codex/skills/value-investing/SKILL.md"
test -f "$HOME/.codex/skills/investment-ranking/SKILL.md"
```

Job logs are stored at:

```text
storage/staging/job-{id}/{instrument-name}/codex.stdout.jsonl
storage/staging/job-{id}/{instrument-name}/codex.stderr.log
```

## Database migrations

```bash
pnpm db:migrate
```

To back up the local database manually:

```bash
mkdir -p storage/backups
sqlite3 storage/app.db ".backup storage/backups/app-$(date +%Y%m%d-%H%M%S).db"
```

This command requires the `sqlite3` CLI, which is not needed for ordinary installation.

## Development checks

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

End-to-end tests:

```bash
pnpm test:e2e
```

## Common failures

| Symptom | Check |
|---|---|
| Jobs remain queued | Confirm the worker is running and inspect the `jobs` status |
| The page shows stale rankings | Check the job failure reason and connectivity to the Tencent quote source |
| Codex exits with a non-zero code | Inspect `codex.stderr.log`, `ai_runs`, and `codex login status` |
| Codex reports that a Skill cannot be found | Check global links using [Codex Skill setup](CODEX_SKILLS.md) |
| The API is unreachable | Check `127.0.0.1:8000/health` and the `pnpm dev:api` logs |
| The page is unreachable | Check `127.0.0.1:5173` and the `pnpm dev:web` logs |
| A candidate is missing from rankings | Check whether it is still awaiting review or has been approved |
| Nothing runs on a market holiday | Check the trading calendar and timezone in the schedule settings |
