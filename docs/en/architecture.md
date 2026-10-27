<p align="center">
  <a href="../architecture.md">简体中文</a>
  &nbsp;|&nbsp;
  <a href="./architecture.md"><strong>English</strong></a>
</p>

# System Architecture

> **Scope:** The project is currently developed and validated primarily for the A-share market and Linux. The AI valuation logic itself is not market-specific. Non-A-share markets and non-Linux environments have not been tested; verify them yourself and use them at your own risk. The project follows a long-term value-investing approach: buy good companies at reasonable or cheap prices and hold them for the long term; it is not intended for short-term speculation.

## Runtime units

| Process | Responsibility |
|---|---|
| `web` | Vue 3 + Naive UI SPA for rankings, in-page details, schedules, and review status |
| `api` | FastAPI service for queries and job submission |
| `scheduler` | Checks schedules against the trading calendar and creates idempotent jobs |
| `worker` | Runs market refreshes or Codex valuation jobs |

In development, `pnpm dev` at the repository root starts all four processes. The API defaults to `127.0.0.1:8000`, and the frontend defaults to `127.0.0.1:5173`.

## Data boundaries

```text
read-only inputs
  LEGACY_DATA_DIR/*.json (default: ../data)
  LEGACY_COMMON_DIR or storage/common/*.json

runtime source of truth
  storage/app.db

immutable artifacts
  storage/staging/
```

The database is the source of truth for web queries. Valuation cards are an import, export, and audit format. Complete frontend details render dynamically from the database; no per-instrument HTML is stored.

## Key tables

| Table | Description |
|---|---|
| `instruments` / `listings` | Instruments and "instrument × market" listing units |
| `valuation_reports` | Immutable valuation report versions and publication status |
| `valuation_markets` | Per-market fair-value ranges, returns, drawdowns, and position sizing |
| `quote_observations` | Market quote snapshots |
| `macro_observations` | Facts such as interest rates, exchange rates, and A/H premiums |
| `ranking_runs` / `ranking_entries` | Ranking runs and four-dimensional score snapshots |
| `schedule_settings` | Automatic update schedules |
| `job_runs` | Job states, idempotency keys, and structured results |
| `ai_runs` | Codex CLI versions, logs, and candidate-artifact records |

## Ranking updates

1. Select the latest published valuation version for each instrument.
2. Calculate the current margin of safety using the latest quotes.
3. Replace the previous risk-free rate with the latest macro data.
4. Calculate all three rankings using the existing `investment-ranking` methodology.
5. Persist a `ranking_run` without modifying historical valuation reports.

## Codex valuation

1. The API creates a `valuation_refresh` job.
2. The worker creates `storage/staging/job-{id}/`.
3. It copies `common/`, writes the previous valuation card, latest quote evidence, and the prompt.
4. `codex exec` runs in the isolated directory and is instructed to invoke the `value-investing` Skill. The Codex runtime must be able to see the project-level or global Skill; see [Codex Skill setup](CODEX_SKILLS.md).
5. Python validates the exit code, valuation-card schema, dates, and instrument name.
6. The candidate report is stored with `needs_review` status.
7. Only a manual approval changes it to `published` and triggers ranking recalculation.

## Failure policy

- A partial quote-source failure marks the job `partial`; quotes that were retrieved can still be stored.
- If no valid quotes are retrieved for the whole run, the job fails and the previous rankings remain readable.
- A Codex timeout, abnormal exit, or invalid artifact rejects the candidate and keeps it out of rankings.
- Database idempotency keys prevent duplicate jobs from synchronized or repeated scheduler triggers.
