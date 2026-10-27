<p align="center">
  <a href="../QUICKSTART.md">简体中文</a>
  &nbsp;|&nbsp;
  <a href="./QUICKSTART.md"><strong>English</strong></a>
</p>

# Quick Start

This guide is for first-time contributors. It covers dependency installation, database initialization, and starting the API, web application, worker, and scheduler on a clean development machine.

> **Scope:** The project is currently developed and validated primarily for the A-share market and Linux. The AI valuation logic itself is not market-specific. Non-A-share markets and non-Linux environments have not been tested; verify them yourself and use them at your own risk. The project follows a long-term value-investing approach: buy good companies at reasonable or cheap prices and hold them for the long term; it is not intended for short-term speculation.

## 1. Install system dependencies

Required:

| Dependency | Version |
|---|---|
| Git | Any recent version |
| Python | 3.12+ |
| Node.js | 22+, with 22 LTS recommended |
| pnpm | 11.10.0, as declared by `packageManager` |
| SQLite | Bundled with Python; the `sqlite3` CLI is optional |
| Codex CLI | Required only for AI valuation |

On Ubuntu 24.04, install the base tools first:

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv curl
python3.12 --version
```

On macOS, Homebrew can be used:

```bash
brew install git python@3.12 node
python3.12 --version
```

After installing Node.js 22+, enable pnpm. The Corepack bundled with Node.js is the simplest option:

```bash
corepack enable
corepack prepare pnpm@11.10.0 --activate
pnpm --version
```

If Corepack is unavailable, install pnpm directly:

```bash
npm install --global pnpm@11.10.0
pnpm --version
```

The project commands use a Node launcher that supports Linux, macOS, and native Windows virtual-environment paths. Codex background jobs use POSIX process-group management, so WSL2 is still recommended for AI valuation on Windows.

## 2. Get the code

```bash
git clone <repository-url>
cd valuation-web
```

Run the remaining commands from the repository root. When `.env` is missing, bootstrap copies it from `.env.example`. The default database is `storage/app.db` inside the repository, so no separate database server is required.

## 3. Install project dependencies

One command creates the Python virtual environment, installs backend and frontend dependencies, and runs database migrations:

```bash
pnpm run bootstrap
```

This step:

1. Creates `.venv`.
2. Installs `apps/api[dev]`.
3. Installs frontend dependencies from `pnpm-lock.yaml`.
4. Creates the `storage/` runtime directory.
5. Runs Alembic migrations.
6. Idempotently imports historical valuation cards when the default `../data` directory exists; otherwise, it skips the import.

The command automatically detects `.venv/bin/python` or `.venv/Scripts/python.exe`; you do not need to set `PYTHONPATH` manually. Use pnpm scripts as the cross-platform entry points.

Bootstrap isolates any existing `PYTHONPATH` and `PYTHONHOME` settings in the shell, preventing ROS, Conda, or other Python environments from injecting packages into the project virtual environment.

## 4. Prepare the Codex Skill (optional)

You can skip this section when working only on rankings, valuation details, and ordinary market refreshes. Starting a new Codex valuation requires:

```bash
codex --version
codex login
codex login status
```

The project Skills live in `.codex/skills/`. Codex can usually read them when launched from the repository root. To ensure the worker can also find both Skills while running in `storage/staging/` subdirectories, install global symbolic links for the current development account:

```bash
mkdir -p "$HOME/.codex/skills"
ln -sfn "$PWD/.codex/skills/value-investing" \
  "$HOME/.codex/skills/value-investing"
ln -sfn "$PWD/.codex/skills/investment-ranking" \
  "$HOME/.codex/skills/investment-ranking"
```

Verify:

```bash
test -f "$HOME/.codex/skills/value-investing/SKILL.md"
test -f "$HOME/.codex/skills/investment-ranking/SKILL.md"
codex login status
```

See the official Codex CLI documentation for installation instructions: <https://developers.openai.com/codex/>. For project-specific Skill details, see [Codex Skill setup](CODEX_SKILLS.md).

## 5. Start the development services

```bash
pnpm dev
```

This starts four processes in parallel:

| Process | Address or responsibility |
|---|---|
| Web | <http://127.0.0.1:5173> |
| API | <http://127.0.0.1:8000> |
| OpenAPI | <http://127.0.0.1:8000/docs> |
| worker | Processes market refresh and valuation jobs |
| scheduler | Creates scheduled jobs for trading days |

Open the web address in a browser. Press `Ctrl+C` to stop all four development processes.

You can also start processes individually when you need to inspect their logs:

```bash
pnpm dev:api
pnpm dev:web
pnpm dev:worker
pnpm dev:scheduler
```

## 6. Verify the installation

In another terminal, run the following from the repository root:

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/api/v1/schedule
```

The health check should return:

```json
{"status":"ok","environment":"development"}
```

An empty database is valid: the web application opens without instruments or rankings. Add an instrument through the web interface or import the example valuation cards:

```bash
node scripts/python.mjs -m app.cli import-legacy \
  --data-dir schemas/value-investing/examples
```

You can also import a directory of schema 1.0–1.2 valuation cards:

```bash
node scripts/python.mjs -m app.cli import-legacy \
  --data-dir /absolute/path/to/cards
```

## 7. Development checks

Before committing, run at least the checks relevant to your change. The full check suite is:

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

End-to-end tests use Playwright and the local Edge browser:

```bash
pnpm test:e2e
```

## 8. Troubleshooting

| Symptom | Resolution |
|---|---|
| `python3` is not version 3.12 | Install Python 3.12, or specify an interpreter with `PYTHON=/absolute/path/to/python3.12 pnpm run bootstrap` |
| `pnpm: command not found` | Enable Corepack or install `pnpm@11.10.0` |
| pnpm reports a version mismatch | Run `corepack prepare pnpm@11.10.0 --activate`; avoid mixing pnpm versions |
| `../data` does not exist | This is normal; installation skips the historical import. You can also change `LEGACY_DATA_DIR` |
| Port 5173 or 8000 is in use | Stop the old process or temporarily change the port in the relevant startup command |
| Codex reports `Not logged in` | Run `codex login`, then check `codex login status` |
| Codex cannot find a Skill | Ensure both Skills are under `$HOME/.codex/skills/` and their entry file is named `SKILL.md` |
| `bootstrap` cannot find Python | Set `PYTHON` to a Python 3.12 executable, or check `py -3.12 --version` on Windows |
| pip reports conflicts with external packages such as `launch-ros` | Use the latest bootstrap and do not manually add ROS site-packages to the project `PYTHONPATH` |
| The page keeps failing to load | Confirm all four `pnpm dev` processes are running and check the API `/health` endpoint |
| Jobs remain queued | Confirm the worker is running; do not start only `pnpm dev:web` |

For daily operations, see the [operations runbook](runbook.md). For dependency details, see [Dependencies](DEPENDENCIES.md).
