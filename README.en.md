<p align="center">
  <a href="./README.md">简体中文</a>
  &nbsp;|&nbsp;
  <a href="./README.en.md"><strong>English</strong></a>
</p>

# Valuation Radar

Valuation Radar is a local-first value-investing research workspace centered on AI-assisted valuation, with a complete web interface. Codex-driven valuation workflows research and value individual stocks and ETFs systematically, then combine market data, risk preferences, and expected returns into multiple rankings. Valuation reasoning, supporting data, candidate results, and historical versions can all be inspected, reviewed, and traced in the web application.

The project turns valuation cards, three risk-preference rankings, and valuation reports into a queryable, auditable web application that can be refreshed on trading days.

Valuation Radar is open source under the [GNU General Public License v3.0](LICENSE) (`GPL-3.0-only`). Third-party dependencies, model services, and market-data providers remain subject to their respective licenses and terms of service. See [Dependencies](docs/en/DEPENDENCIES.md) for details.

## Supported markets and environments

The project is currently developed and validated primarily for the A-share market and the Linux environment. The AI valuation logic itself is not market-specific, but non-A-share markets and non-Linux environments have not been tested. They may work in principle; verify them yourself and use them at your own risk.

Valuation Radar is built around long-term value investing: buy good companies at reasonable or cheap prices and hold them for the long term. It is not intended for short-term speculation.

## Screenshots

### Risk-adjusted value rankings

![Risk-adjusted value rankings](docs/screenshots/dashboard.png)

### In-page valuation details

![Valuation details](docs/screenshots/valuation-detail.png)

### Data updates and runtime status

![Data updates and runtime status](docs/screenshots/updates.png)

### Candidate valuation preview

![Candidate valuation preview](docs/screenshots/review-preview.png)

## Features

- Vue 3 ranking dashboard with conservative, balanced, and aggressive rankings, top-three picks, a scatter chart, filters, and the full ranking table.
- Complete in-page valuation details: selecting a ranking entry opens fair-value range, current margin of safety, return breakdown, four-dimensional scoring, position sizing, risks, and A/H comparison.
- SQLite data layer for historical valuation versions, market snapshots, quotes, macro data, ranking snapshots, jobs, and AI run records.
- Automatic post-close updates with a trading calendar, configurable scheduling, quote retrieval, idempotent jobs, and ranking recalculation.
- Persistent Codex sessions: the first run stores a `thread_id`; paused, interrupted, or restarted jobs continue through `codex exec resume` with the original session and working directory, avoiding repeated research and calculations.
- Job lifecycle management: valuation jobs can be paused, resumed, deleted individually, and tracked by cumulative runtime. Deleting a running job terminates its Codex process group before cleaning up records and staging data.
- End-to-end Codex valuation workflow: an isolated staging directory invokes the `value-investing` skill, Python validates the output, and the result enters a manual review queue. Multiple runs of the same job appear as one logical session in Debug while preserving per-run audit details.
- Candidate review: pending cards open in a full valuation preview with approval and rejection controls pinned to the bottom. Rejected candidates can be previewed, re-valued, or permanently deleted.
- ETF data constraints: validation covers top-ten constituent weights, representative PB harmonic mean, synchronized NAV and price dates, premium/discount rate, and report-section structure to reduce unauditable ETF valuations.
- Manual instrument entry: create a valuation job from the dashboard by name, with an optional security code. Codex discovers the listing market when no code is supplied, and A/H dual-listed companies are researched in both markets by default.
- Instrument lifecycle: the instrument library supports removing an instrument from rankings, restoring it, and permanent deletion after name confirmation. Archiving retains full valuation history, while permanent deletion also removes related jobs and staging directories.

## Technology stack

- Frontend: Vue 3, TypeScript, Vite, Vue Router, Naive UI with its dark theme, TanStack Vue Query, and ECharts
- Backend: FastAPI, Pydantic v2, SQLAlchemy 2, and Alembic
- Database: SQLite with WAL mode
- Scheduling: a standalone scheduler, a single-instance worker, and database-backed job tables
- Model integration (optional): the Codex CLI `exec` command in a working-directory sandbox, with no direct writes to the production database

See [docs/en/architecture.md](docs/en/architecture.md) for architecture details and
`.codex/skills/value-investing/references/card-v1.2.schema.json` for the
valuation-card contract.

Visual styling is centralized in `apps/web/src/theme.ts` and `apps/web/src/styles/`: theme tokens, page layouts, and brand-specific component styles live in dedicated files instead of scattered custom rules inside page components.

## Documentation

| Document | Purpose |
|---|---|
| [Quick Start](docs/en/QUICKSTART.md) | Install dependencies, initialize the database, and start local services from scratch |
| [Dependencies](docs/en/DEPENDENCIES.md) | Development versions, lockfiles, external services, and license boundaries |
| [Codex Skill setup](docs/en/CODEX_SKILLS.md) | Project-level and global Skill installation, login, and verification |
| [Operations runbook](docs/en/runbook.md) | Local health checks, job handling, and database migrations |
| [System architecture](docs/en/architecture.md) | Processes, data boundaries, and the Codex valuation job pipeline |

## TODO

- [ ] Add a Simplified Chinese / English language switch to the web UI, covering navigation, forms, statuses, errors, dates, and number formatting.
- [ ] Evaluate a bilingual data contract and model-output strategy for valuation report bodies and section titles.

## Quick Start

The base UI, data import, rankings, and quote refresh require Python 3.12, Node.js 22+, pnpm 11.10, and SQLite. The Codex CLI is required only when starting a Codex valuation from the web interface.

```bash
pnpm run bootstrap
pnpm dev
```

Open:

- Web: <http://127.0.0.1:5173>
- API: <http://127.0.0.1:8000>
- OpenAPI: <http://127.0.0.1:8000/docs>

See the [Quick Start](docs/en/QUICKSTART.md) for full system setup, Codex login, Skill installation, sample-data import, and troubleshooting.

## Common commands

```bash
pnpm dev             # API, web app, worker, and scheduler
pnpm test            # Backend and frontend unit tests
pnpm test:e2e        # Edge desktop and mobile end-to-end tests
pnpm lint            # Ruff + ESLint
pnpm typecheck       # mypy + vue-tsc
pnpm build           # Production frontend build
pnpm db:migrate      # Run Alembic migrations
pnpm import:legacy   # Re-imports are idempotent
```

## Data flow

```text
data/*.json
        ↓ import and validation
SQLite historical valuation versions
        ↓ four-dimensional scoring
three ranking snapshots

after market close → scheduler → job_runs → worker
                                             ├─ quote/macro writes → ranking rebuild
                                             ├─ Codex persistent session ─┬─ pause / resume
                                             │                            ├─ resume after interruption
                                             │                            └─ terminate and delete
                                             └─ candidate validation → preview and review
                                                                          ├─ approve → publish and rebuild rankings
                                                                          └─ reject → retain or delete
```

Latest quotes only update the current margin of safety and rankings; they never rewrite historical fair-value anchors. Codex results do not enter current rankings before approval. Pausing, interrupting, and resuming do not reset cumulative runtime; a new Codex session is used only when the working directory or persistent session is unavailable.

## Data and security

- The web development server listens on `0.0.0.0`, allowing access from the local network. The API still listens only on `127.0.0.1`, and browser requests are forwarded through Vite's `/api` proxy.
- Databases, logs, archives, and staging directories are excluded from Git.
- Model runs execute in the isolated `storage/staging/` directory with the `workspace-write` sandbox.
- Codex sessions are persisted by the local Codex CLI. Deleting a job terminates its process group and removes the job's staging directory.
- A new valuation stops immediately when required data is missing; no candidate card is generated or published. Historical cards receive read-only compatibility handling.
- The application has no built-in authentication and should be used only in a local development environment. Do not expose it to the public internet.
- Quotes, macro data, and model output depend on external service availability, account permissions, and terms of service.
- All analysis is for research only and does not constitute investment advice.

## Acknowledgements

Valuation Radar would not be possible without the support of the following people and projects:

- Thanks to Codex for collaborating on valuation workflow design and software development.
- Thanks to Uncle Liang for the DeepSeek support.
- Thanks to Vue and Naive UI for providing reliable and approachable frontend foundations.

## Join the development

We welcome anyone interested in value-investing tools, AI-assisted valuation, frontend experience, backend engineering, or documentation to join the development of Valuation Radar. Start with the [Quick Start](docs/en/QUICKSTART.md) and run the project locally, open an Issue to discuss ideas, or submit a focused Pull Request with the necessary tests and documentation.

Before submitting code, run `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build`. For UI interaction changes, also run the relevant `pnpm test:e2e` cases.

## License

Copyright (C) 2026 Valuation Radar contributors.

This project is licensed solely under the GNU General Public License v3.0 (SPDX: `GPL-3.0-only`) and does not automatically apply any later version. You may use, modify, and distribute the project under the terms of [LICENSE](LICENSE); distributing modified versions also requires satisfying the GPL source-code availability requirements. Unless otherwise noted, contributions submitted to this project are licensed under the same terms.
