# Codex Skill 安装

估值雷达包含两个版本化的项目 Skill：

| Skill | 路径 | 职责 |
|---|---|---|
| `value-investing` | `.codex/skills/value-investing/` | 检索证据、估值、生成并校验 schema 1.2 数据卡 |
| `investment-ranking` | `.codex/skills/investment-ranking/` | 读取数据卡，生成三套风险偏好的离线排序 JSON |

Codex 的官方 Skill 说明见 <https://developers.openai.com/codex/skills>。本文只说明本地开发时如何让 CLI 和 worker 找到这两个 Skill。

## 1. 项目级 Skill

两个 Skill 已经随仓库放在 `.codex/skills/`，不需要在仓库内重复安装。直接在仓库根目录使用 Codex，或在仓库内打开 Codex，就可以读取它们。

Codex 的入口文件必须命名为 `SKILL.md`，目录名与 frontmatter 里的 `name` 保持一致。正常情况下不需要修改 `$CODEX_HOME`。

## 2. 安装到当前开发账户

后端 worker 会把 Codex 的当前目录设为 `storage/staging/job-*`。为保证子目录执行时也能发现 Skill，推荐把仓库中的两个 Skill 链接到当前开发账户的全局目录：

```bash
mkdir -p "$HOME/.codex/skills"

ln -sfn "$PWD/.codex/skills/value-investing" \
  "$HOME/.codex/skills/value-investing"
ln -sfn "$PWD/.codex/skills/investment-ranking" \
  "$HOME/.codex/skills/investment-ranking"
```

命令必须在仓库根目录执行，`$PWD` 会展开为当前仓库路径。如果目标位置已经有真实目录而不是符号链接，`ln` 会安全失败；先人工确认并移走旧目录，再重新执行。

符号链接的好处是切换分支或 `git pull` 后立即使用仓库里的新版本，不需要重复复制。

两个 Skill 应一起安装。`investment-ranking` 通过相邻的 `value-investing` 目录加载 schema 和校验脚本；只安装其中一个会导致离线排序或校验路径失败。

## 3. 登录 Codex

Codex CLI 的安装方式以官方文档为准：<https://developers.openai.com/codex/>。

```bash
codex --version
codex login
codex login status
```

AI 估值任务使用启动 worker 的账户所持有的 Codex 登录态。开发时通常就是当前登录用户，不需要额外切换账户。

不要把 `$CODEX_HOME`、`auth.json`、shell 历史或导出令牌写入仓库和日志。若 `.env` 中需要指定 CLI 路径，可使用：

```dotenv
CODEX_BINARY=/absolute/path/to/codex
```

## 4. 验证安装

```bash
test -f "$PWD/.codex/skills/value-investing/SKILL.md"
test -f "$PWD/.codex/skills/investment-ranking/SKILL.md"
test -f "$HOME/.codex/skills/value-investing/SKILL.md"
test -f "$HOME/.codex/skills/investment-ranking/SKILL.md"
```

项目的 schema 校验脚本依赖 `.venv` 中的 `jsonschema`：

```bash
node scripts/python.mjs .codex/skills/value-investing/scripts/scorecard.py list \
  --dir schemas/value-investing/examples
```

预期能看到 `card-v1.2.example.json`。然后在 Codex 中显式调用一次：

```text
请使用 $value-investing 对测试标的做一次完整估值，并输出 schema 1.2 数据卡。
```

后端任务的 prompt 已经显式要求使用 `value-investing`。自动触发描述主要用于手工对话。

## 5. 修改 Skill

| 修改内容 | 文件 |
|---|---|
| 触发描述、主流程、硬性输出规则 | `SKILL.md` |
| 数据卡 schema 与 presentation 契约 | `references/` |
| 校验、评分、缓存脚本 | `scripts/` |
| 展示名和默认提示 | `agents/openai.yaml` |

修改 `SKILL.md` 或 `references/` 后无需重新编译。使用符号链接安装时会直接读取新文件。

Skill 与 Web 后端共同消费 schema 1.2。修改 schema、评分字段或展示区块时，必须同步运行：

```bash
pnpm test:api
pnpm test:web
pnpm typecheck
```

候选卡通过 Python 校验后才会进入复核队列，但校验通过不等于估值结论正确。正式发布仍需要人工复核。

## 6. 常见问题

| 现象 | 排查 |
|---|---|
| `Not logged in` | 执行 `codex login`，再运行 `codex login status` |
| 找不到 `$value-investing` | 检查 `$HOME/.codex/skills`、`SKILL.md` 文件名和 frontmatter |
| 只找到 value-investing | 同时安装 `investment-ranking`，保持两个目录相邻 |
| 分支切换后 Skill 未更新 | 确认全局位置是指向当前仓库的符号链接 |
| Skill 脚本报缺少 `jsonschema` | 使用 `node scripts/python.mjs`，并重新执行 `pnpm run bootstrap` |
| Codex 无网络 | 检查代理、DNS、CA；先访问 `https://qt.gtimg.cn/q=sh600941` |
| 旧会话恢复失败 | 检查 `thread_id`、原工作目录和 Codex 会话目录是否仍存在 |
| 任务删除后仍有 Codex 子进程 | 查看对应 `codex.stderr.log`，并重启 `pnpm dev` |

Skill 可以发现并读取文件，也可能按照其流程联网取证。只安装经过审查的 Skill，并保持 Codex 的 `workspace-write` 沙箱。
