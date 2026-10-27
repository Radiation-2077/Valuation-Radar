<p align="center">
  <a href="../CODEX_SKILLS.md">简体中文</a>
  &nbsp;|&nbsp;
  <a href="./CODEX_SKILLS.md"><strong>English</strong></a>
</p>

# Codex Skill Setup

Valuation Radar contains two versioned project Skills:

| Skill | Path | Responsibility |
|---|---|---|
| `value-investing` | `.codex/skills/value-investing/` | Gather evidence, value an instrument, and generate and validate schema 1.2 valuation cards |
| `investment-ranking` | `.codex/skills/investment-ranking/` | Read valuation cards and generate offline ranking JSON for three risk preferences |

See the official Codex Skill documentation at <https://developers.openai.com/codex/skills>. This guide only explains how to make the CLI and worker discover these two Skills during local development.

> **Scope:** The instructions below primarily target Linux. The AI valuation logic is not market-specific, but non-A-share markets and non-Linux environments have not been tested; verify them yourself and use them at your own risk. The project follows a long-term value-investing approach: buy good companies at reasonable or cheap prices and hold them for the long term; it is not intended for short-term speculation.

## 1. Project-level Skills

Both Skills are already versioned in `.codex/skills/` and do not need to be installed again inside the repository. Launch Codex from the repository root, or open Codex inside the repository, and it can read them directly.

The Codex entry file must be named `SKILL.md`, and the directory name must match `name` in the frontmatter. Normally, `$CODEX_HOME` does not need to be changed.

## 2. Install for the current development account

The backend worker sets Codex's working directory to `storage/staging/job-*`. To make the Skills discoverable from those subdirectories, link both repository Skills into the current development account's global Skill directory:

```bash
mkdir -p "$HOME/.codex/skills"

ln -sfn "$PWD/.codex/skills/value-investing" \
  "$HOME/.codex/skills/value-investing"
ln -sfn "$PWD/.codex/skills/investment-ranking" \
  "$HOME/.codex/skills/investment-ranking"
```

Run these commands from the repository root so `$PWD` expands to the current repository path. If the target already contains a real directory rather than a symbolic link, `ln` exits safely. Inspect and move the old directory before retrying.

Symbolic links use the latest repository version immediately after switching branches or running `git pull`, without copying files again.

Install both Skills together. `investment-ranking` loads schemas and validation scripts from the adjacent `value-investing` directory; installing only one can break offline ranking or validation paths.

## 3. Log in to Codex

See the official documentation for Codex CLI installation: <https://developers.openai.com/codex/>.

```bash
codex --version
codex login
codex login status
```

AI valuation jobs use the Codex login state of the account that starts the worker. During development, this is usually the current user, with no separate account switch required.

Never write `$CODEX_HOME`, `auth.json`, shell history, or exported tokens into the repository or logs. If `.env` must specify the CLI path, use:

```dotenv
CODEX_BINARY=/absolute/path/to/codex
```

## 4. Verify the installation

```bash
test -f "$PWD/.codex/skills/value-investing/SKILL.md"
test -f "$PWD/.codex/skills/investment-ranking/SKILL.md"
test -f "$HOME/.codex/skills/value-investing/SKILL.md"
test -f "$HOME/.codex/skills/investment-ranking/SKILL.md"
```

The project schema validation script depends on `jsonschema` from `.venv`:

```bash
node scripts/python.mjs .codex/skills/value-investing/scripts/scorecard.py list \
  --dir schemas/value-investing/examples
```

`card-v1.2.example.json` should appear. Then invoke the Skill explicitly in Codex:

```text
Use $value-investing to produce a complete valuation for the test instrument and output a schema 1.2 valuation card.
```

Backend job prompts already require `value-investing`. The trigger description is mainly used in manual conversations.

## 5. Modify a Skill

| Change | File |
|---|---|
| Trigger description, main workflow, and hard output rules | `SKILL.md` |
| Valuation-card schema and presentation contract | `references/` |
| Validation, scoring, and cache scripts | `scripts/` |
| Display name and default prompt | `agents/openai.yaml` |

No recompilation is needed after changing `SKILL.md` or `references/`. Symbolic-link installations read the new files directly.

The Skills and web backend both consume schema 1.2. When changing the schema, scoring fields, or presentation blocks, also run:

```bash
pnpm test:api
pnpm test:web
pnpm typecheck
```

Candidate cards enter the review queue only after passing Python validation, but passing validation does not prove that a valuation conclusion is correct. Publishing still requires manual review.

## 6. Troubleshooting

| Symptom | Check |
|---|---|
| `Not logged in` | Run `codex login`, then `codex login status` |
| `$value-investing` cannot be found | Check `$HOME/.codex/skills`, the `SKILL.md` filename, and frontmatter |
| Only `value-investing` is found | Install `investment-ranking` as well and keep both directories adjacent |
| Skills do not update after switching branches | Confirm the global paths are symbolic links into the current repository |
| A Skill script reports missing `jsonschema` | Use `node scripts/python.mjs` and rerun `pnpm run bootstrap` |
| Codex has no network access | Check the proxy, DNS, and CA configuration; first try `https://qt.gtimg.cn/q=sh600941` |
| Resuming an old session fails | Check that `thread_id`, the original working directory, and the Codex session directory still exist |
| A Codex child process remains after job deletion | Inspect the matching `codex.stderr.log` and restart `pnpm dev` |

Skills can discover and read files and may gather evidence online according to their workflows. Install only Skills you have reviewed and keep Codex inside the `workspace-write` sandbox.
