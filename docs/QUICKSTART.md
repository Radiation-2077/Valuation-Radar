# Quick Start

本文面向第一次参与开发的成员，目标是在一台干净的 Linux 或 macOS 开发机上完成依赖安装、数据库初始化，并启动 API、Web、worker 和 scheduler。

## 1. 准备系统依赖

需要：

| 依赖 | 版本 |
|---|---|
| Git | 任意近期版本 |
| Python | 3.12+ |
| Node.js | 22+，推荐 22 LTS |
| pnpm | 11.10.0，由 `packageManager` 声明 |
| SQLite | Python 自带；`sqlite3` CLI 可选 |
| Codex CLI | 仅 AI 估值需要 |

Ubuntu 24.04 可先安装基础工具：

```bash
sudo apt update
sudo apt install -y git python3.12 python3.12-venv curl
python3.12 --version
```

macOS 可使用 Homebrew：

```bash
brew install git python@3.12 node
python3.12 --version
```

安装 Node.js 22+ 后启用 pnpm。Node 自带的 Corepack 最方便：

```bash
corepack enable
corepack prepare pnpm@11.10.0 --activate
pnpm --version
```

如果系统没有 Corepack，也可以直接安装：

```bash
npm install --global pnpm@11.10.0
pnpm --version
```

项目命令通过 Node 启动器兼容 Linux、macOS 和原生 Windows 的虚拟环境目录。由于 Codex 后台任务使用 POSIX 进程组管理，Windows 上执行 AI 估值仍建议使用 WSL2。

## 2. 获取代码

```bash
git clone <repository-url>
cd valuation-web
```

后续命令都从仓库根目录执行。bootstrap 会在缺少 `.env` 时自动从 `.env.example` 复制，默认使用仓库内的 `storage/app.db`，不需要另装数据库服务。

## 3. 安装项目依赖

一条命令完成 Python 虚拟环境、前后端依赖和数据库迁移：

```bash
pnpm run bootstrap
```

这一步会执行：

1. 创建 `.venv`。
2. 安装 `apps/api[dev]`。
3. 按 `pnpm-lock.yaml` 安装前端依赖。
4. 创建 `storage/` 运行目录。
5. 执行 Alembic 迁移。
6. 如果默认的 `../data` 存在，则幂等导入历史数据卡；目录不存在时自动跳过。

该命令会自动识别 `.venv/bin/python` 或 `.venv/Scripts/python.exe`，不需要手动设置 `PYTHONPATH`。项目统一以 pnpm 脚本作为跨平台入口。

bootstrap 会隔离 shell 中已有的 `PYTHONPATH` 和 `PYTHONHOME`，避免 ROS、Conda 或其他 Python 环境把包注入项目虚拟环境。

## 4. 准备 Codex Skill（可选）

如果只开发排名、详情和普通行情刷新，可以先跳过本节。发起新的 Codex 估值需要：

```bash
codex --version
codex login
codex login status
```

项目 Skill 位于 `.codex/skills/`。从仓库根目录使用 Codex 时通常可以直接读取；为保证 worker 在 `storage/staging/` 子目录执行任务时也能找到两个 Skill，建议给当前开发账户安装全局符号链接：

```bash
mkdir -p "$HOME/.codex/skills"
ln -sfn "$PWD/.codex/skills/value-investing" \
  "$HOME/.codex/skills/value-investing"
ln -sfn "$PWD/.codex/skills/investment-ranking" \
  "$HOME/.codex/skills/investment-ranking"
```

验证：

```bash
test -f "$HOME/.codex/skills/value-investing/SKILL.md"
test -f "$HOME/.codex/skills/investment-ranking/SKILL.md"
codex login status
```

Codex CLI 的安装方式以官方文档为准：<https://developers.openai.com/codex/>。项目 Skill 的详细说明见 [Codex Skill 安装](CODEX_SKILLS.md)。

## 5. 启动开发服务

```bash
pnpm dev
```

该命令会并行启动：

| 进程 | 地址/职责 |
|---|---|
| Web | <http://127.0.0.1:5173> |
| API | <http://127.0.0.1:8000> |
| OpenAPI | <http://127.0.0.1:8000/docs> |
| worker | 消费行情刷新和估值任务 |
| scheduler | 创建交易日定时任务 |

浏览器打开 Web 地址即可。按 `Ctrl+C` 会一并停止四个开发进程。

也可以分别启动，便于查看日志：

```bash
pnpm dev:api
pnpm dev:web
pnpm dev:worker
pnpm dev:scheduler
```

## 6. 验证安装

另开一个终端，从仓库根目录执行：

```bash
curl -fsS http://127.0.0.1:8000/health
curl -fsS http://127.0.0.1:8000/api/v1/schedule
```

健康检查应返回：

```json
{"status":"ok","environment":"development"}
```

如果数据库为空，页面可以正常打开，但没有标的和排名。这是正常状态，可以通过 Web 添加标的，或导入示例数据卡：

```bash
node scripts/python.mjs -m app.cli import-legacy \
  --data-dir schemas/value-investing/examples
```

也可以导入自己的 schema 1.0–1.2 数据卡目录：

```bash
node scripts/python.mjs -m app.cli import-legacy \
  --data-dir /absolute/path/to/cards
```

## 7. 开发检查

提交前至少运行与改动相关的检查。完整检查命令：

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

端到端测试使用 Playwright 和本机 Edge：

```bash
pnpm test:e2e
```

## 8. 常见问题

| 现象 | 处理 |
|---|---|
| `python3` 不是 3.12 | 安装 Python 3.12；也可用 `PYTHON=/absolute/path/to/python3.12 pnpm run bootstrap` 指定解释器 |
| `pnpm: command not found` | 启用 Corepack，或安装 `pnpm@11.10.0` |
| pnpm 报版本不匹配 | 执行 `corepack prepare pnpm@11.10.0 --activate`，不要混用多个 pnpm 版本 |
| `../data` 不存在 | 正常，安装会跳过历史导入；也可修改 `LEGACY_DATA_DIR` |
| 5173 或 8000 端口被占用 | 停止旧进程，或临时修改对应启动命令中的端口 |
| Codex 提示 `Not logged in` | 执行 `codex login`，再检查 `codex login status` |
| Codex 找不到 Skill | 确认两个 Skill 都在 `$HOME/.codex/skills/`，且入口文件名为 `SKILL.md` |
| `bootstrap` 找不到 Python | 设置 `PYTHON` 指向 Python 3.12 可执行文件，或检查 Windows 的 `py -3.12 --version` |
| pip 报 `launch-ros` 等外部依赖冲突 | 确认使用最新 bootstrap；不要手动把 ROS 的 site-packages 加进项目 `PYTHONPATH` |
| 页面一直加载失败 | 确认 `pnpm dev` 的四个进程都在运行，并检查 API `/health` |
| 任务一直排队 | 确认 worker 已启动；不要只运行 `pnpm dev:web` |

更多日常操作见 [开发运维](runbook.md)，依赖细节见 [依赖说明](DEPENDENCIES.md)。
