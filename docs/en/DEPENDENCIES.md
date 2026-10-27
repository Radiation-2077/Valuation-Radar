<p align="center">
  <a href="../DEPENDENCIES.md">简体中文</a>
  &nbsp;|&nbsp;
  <a href="./DEPENDENCIES.md"><strong>English</strong></a>
</p>

# Dependencies

This document describes the software, version sources, external services, and license boundaries required to develop Valuation Radar. Repository files are authoritative for versions; the paths below were last checked on 2026-10-27. See [Quick Start](QUICKSTART.md) for installation from scratch.

> **Scope:** The project is currently developed and validated primarily for the A-share market and Linux. The AI valuation logic itself is not market-specific. Non-A-share markets and non-Linux environments have not been tested; verify them yourself and use them at your own risk. The project follows a long-term value-investing approach: buy good companies at reasonable or cheap prices and hold them for the long term; it is not intended for short-term speculation.

## 1. Supported runtime environments

| Item | Recommended version | Purpose | Required |
|---|---|---|---|
| Linux / macOS | Recent versions; WSL2 is recommended on Windows | Development environment | Yes |
| Python | 3.12+ | API, worker, scheduler, and Skill validation scripts | Yes |
| Node.js | 22+, with 22 LTS recommended | Development server, tests, and Vue frontend builds | Yes |
| pnpm | 11.10.0 | Frontend workspace installation and builds | Yes |
| SQLite | Python's built-in SQLite 3 | Runtime database | Yes |
| `sqlite3` CLI | A recent version supplied by the distribution | Inspect or back up the local database manually | Optional |
| Codex CLI | A version supporting the required `codex exec` flags | Start new AI valuations | Required for AI valuation |

The current development baseline has been verified with Python 3.12.3, Node.js 24.14.0, pnpm 11.10.0, and `codex-cli 0.164.0`. Codex CLI changes quickly; the project depends on the following `codex exec` capabilities rather than one exact version:

```text
codex exec --json
codex exec --sandbox workspace-write
codex exec --output-schema <file>
codex exec --output-last-message <file>
codex exec resume <thread-id>
--config sandbox_workspace_write.network_access=true
```

After upgrading Codex CLI, run at least one real valuation job to confirm that these flags, the login state, and Skill discovery still work.

## 2. Python dependencies

Direct Python dependencies and compatibility ranges are declared in [apps/api/pyproject.toml](../../apps/api/pyproject.toml):

| Dependency | Declared range | Responsibility |
|---|---|---|
| FastAPI | `>=0.115,<1` | HTTP API and OpenAPI |
| Pydantic Settings | `>=2.6,<3` | `.env` and runtime configuration |
| SQLAlchemy | `>=2.0.36,<3` | ORM and SQLite access |
| Alembic | `>=1.14,<2` | Database migrations |
| Uvicorn | `>=0.30,<1` | ASGI server |
| APScheduler | `>=3.10,<4` | Scheduling dependency |
| Exchange Calendars | `>=4.6,<5` | Shanghai and Hong Kong exchange calendars |
| httpx | `>=0.28,<1` | Market data, macro data, and Codex network prechecks |
| jsonschema | `>=4.23,<5` | Schema 1.2 valuation-card validation |
| beautifulsoup4 | `>=4.12,<5` | Compatibility parsing for historical HTML reports |

`apps/api[dev]` also installs mypy, pytest, pytest-cov, respx, ruff, and type packages. `pnpm run bootstrap` installs the development extras directly.

Bootstrap and `scripts/python.mjs` isolate external `PYTHONPATH` and `PYTHONHOME` settings, so ROS or Conda packages configured in the shell cannot enter the project virtual environment.

Python dependencies currently use compatibility ranges without a full lockfile. For reproducible builds, generate and archive a tested resolution in CI; do not pin transitive dependencies manually without validation.

## 3. JavaScript dependencies

Direct frontend dependencies and development tools are declared in [apps/web/package.json](../../apps/web/package.json). The complete resolution is locked by [pnpm-lock.yaml](../../pnpm-lock.yaml):

| Dependency | Responsibility |
|---|---|
| Vue 3, Vue Router | SPA and routing |
| Naive UI | Base components and light/dark themes |
| TanStack Vue Query | Server state and request caching |
| ECharts | Ranking and valuation charts |
| KaTeX | Valuation formula rendering |
| Vite, TypeScript, vue-tsc | Development server, builds, and type checking |
| Vitest, Playwright | Unit tests and end-to-end tests |

CI and reproducible local environments should use:

```bash
pnpm install --frozen-lockfile
```

Do not commit a new lockfile immediately after an ordinary install. Upgrade dependencies on a separate branch and verify them with tests.

## 4. External runtime dependencies

These dependencies are not bundled by this repository and cannot be pinned through Python or Node lockfiles:

| Service | Purpose | Configuration or credentials |
|---|---|---|
| Tencent quote API at `qt.gtimg.cn` | A/H quotes and network prechecks before Codex execution | No application key; outbound HTTPS must be allowed |
| Codex model service | New AI valuations, online evidence gathering, and structured-card generation | Provided by the Codex CLI login state or runtime credentials |
| Public quotes, annual reports, and issuer websites | Online valuation evidence gathered by the Skill | Users must verify access and data terms |

Codex login state is usually stored under `$CODEX_HOME` (default: `~/.codex`). It is not a project dependency and must never be copied into the repository or logs. The worker inherits the development account that starts it, so a local `codex login` is sufficient.

If you only use imported valuation cards, rankings, details, and market refreshes, Codex CLI is optional. Market refresh still requires access to the Tencent quote API.

## 5. Filesystem and state

| Path | Content | Notes |
|---|---|---|
| `storage/app.db` | Instruments, reports, quotes, rankings, jobs, and AI audit records | Local runtime source of truth |
| `storage/app.db-wal` and `storage/app.db-shm` | SQLite WAL state files | Managed by SQLite at runtime |
| `storage/common/` | Shared Skill data cache | Safe to rebuild |
| `storage/staging/` | Isolated job directories, Codex logs, and intermediate artifacts | Inspect when debugging jobs |
| `storage/backups/` | Manual backups | Optional |
| `storage/logs/` | Reserved log directory | Terminal output is currently the primary log channel |

The database is the runtime source of truth for web queries. `data/*.json` is an import, export, and audit format, not the live query database.

## 6. License and compliance boundaries

- This project is licensed solely under GNU GPL v3.0 (SPDX: `GPL-3.0-only`) and does not automatically apply a later version. See [LICENSE](../../LICENSE) for the full terms.
- Third-party components such as Vue, FastAPI, SQLAlchemy, and Codex CLI remain subject to their own licenses.
- The repository's GPL license does not replace the terms governing external market data, research reports, model inputs and outputs, or third-party APIs.
- Before use or redistribution, independently review market-data redistribution rights, model-service terms, and licensing requirements in the relevant jurisdiction.
- Use `pnpm licenses list`, `pip-licenses`, or an organizational SBOM tool to produce a detailed dependency inventory for release artifacts.

## 7. Development checklist

```bash
python3 --version
node --version
pnpm --version
codex --version
codex login status
sqlite3 --version

pnpm install --frozen-lockfile
node scripts/python.mjs -m pip check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Dependency upgrades, database migrations, and code changes should be validated together rather than upgrading only part of the stack.
