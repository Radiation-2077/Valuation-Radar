# 依赖说明

本文说明开发估值雷达所需的软件、版本来源、外部服务与许可证边界。版本以仓库文件为准，最后按 2026-10-27 的代码路径核对。从零安装步骤见 [Quick Start](QUICKSTART.md)。

## 1. 支持的运行环境

| 项目 | 建议版本 | 用途 | 是否必需 |
|---|---|---|---|
| Linux / macOS | 近期版本；Windows 建议 WSL2 | 开发环境 | 是 |
| Python | 3.12+ | API、worker、scheduler、Skill 校验脚本 | 是 |
| Node.js | 22+，推荐 22 LTS | 开发生成、测试与构建 Vue 前端 | 是 |
| pnpm | 11.10.0 | 前端工作区安装与构建 | 是 |
| SQLite | Python 内置 SQLite 3 | 运行时数据库 | 是 |
| `sqlite3` CLI | 发行版提供的近期版本 | 人工查看或备份本地数据库 | 可选 |
| Codex CLI | 支持当前 `codex exec` 参数集的版本 | 发起新的 AI 估值 | AI 估值必需 |

当前开发基线已验证 Python 3.12.3、Node.js 24.14.0、pnpm 11.10.0 和 `codex-cli 0.164.0`。Codex CLI 迭代较快，项目真正依赖的是以下 `codex exec` 能力，而不是某个固定版本号：

```text
codex exec --json
codex exec --sandbox workspace-write
codex exec --output-schema <file>
codex exec --output-last-message <file>
codex exec resume <thread-id>
--config sandbox_workspace_write.network_access=true
```

升级 Codex CLI 后，应至少完成一次真实的估值任务，确认上述参数、登录态和 Skill 发现仍然正常。

## 2. Python 依赖

Python 直接依赖及兼容范围定义在 [apps/api/pyproject.toml](../apps/api/pyproject.toml)：

| 依赖 | 声明范围 | 职责 |
|---|---|---|
| FastAPI | `>=0.115,<1` | HTTP API、OpenAPI |
| Pydantic Settings | `>=2.6,<3` | `.env` 与运行配置 |
| SQLAlchemy | `>=2.0.36,<3` | ORM 与 SQLite 访问 |
| Alembic | `>=1.14,<2` | 数据库迁移 |
| Uvicorn | `>=0.30,<1` | ASGI 服务器 |
| APScheduler | `>=3.10,<4` | 调度能力依赖 |
| Exchange Calendars | `>=4.6,<5` | 上交所/港交所交易日历 |
| httpx | `>=0.28,<1` | 行情、宏观数据与 Codex 网络预检 |
| jsonschema | `>=4.23,<5` | schema 1.2 数据卡校验 |
| beautifulsoup4 | `>=4.12,<5` | 兼容历史 HTML 报告解析 |

`apps/api[dev]` 额外安装 mypy、pytest、pytest-cov、respx、ruff 和类型包。`pnpm run bootstrap` 会直接安装开发扩展。

bootstrap 与 `scripts/python.mjs` 会隔离外部 `PYTHONPATH`/`PYTHONHOME`，因此 shell 中同时配置的 ROS 或 Conda 包不会混入项目虚拟环境。

Python 依赖目前使用兼容范围，没有提交全量锁文件。若需要可重复构建，可以在 CI 中生成并归档一份经测试的完整解析结果；不要在未校验的情况下手工固定传递依赖。

## 3. JavaScript 依赖

前端直接依赖及开发工具定义在 [apps/web/package.json](../apps/web/package.json)，完整解析结果由 [pnpm-lock.yaml](../pnpm-lock.yaml) 锁定：

| 依赖 | 职责 |
|---|---|
| Vue 3、Vue Router | SPA 与路由 |
| Naive UI | 基础组件、明暗主题 |
| TanStack Vue Query | 服务端状态与请求缓存 |
| ECharts | 排名与估值图表 |
| KaTeX | 估值公式渲染 |
| Vite、TypeScript、vue-tsc | 开发服务器、构建和类型检查 |
| Vitest、Playwright | 单元与端到端测试 |

CI 和需要可重复安装的本地环境应使用：

```bash
pnpm install --frozen-lockfile
```

不要在普通安装后直接提交新的 lockfile；依赖升级应在独立分支完成并通过测试。

## 4. 外部运行时依赖

这些依赖不由本仓库打包，也不能通过 Python/Node 锁文件固定：

| 服务 | 用途 | 配置/凭证 |
|---|---|---|
| 腾讯行情接口 `qt.gtimg.cn` | A/H 行情与 Codex 执行前网络预检 | 无应用密钥；需允许出站 HTTPS |
| Codex 模型服务 | 新的 AI 估值、联网取证和结构化卡片生成 | 由 Codex CLI 登录态或运行环境凭证提供 |
| 公共行情、年报、证券官网等 | Skill 联网补充估值证据 | 由使用者确认可访问性与数据使用条款 |

Codex 登录信息通常位于 `$CODEX_HOME`（默认 `~/.codex`）中。它不是项目依赖文件，禁止复制进仓库或日志。worker 继承启动它的开发账户，因此本机执行 `codex login` 后即可使用。

如果只使用导入后的数据卡、排名、详情和行情刷新，不发起 AI 估值，可以不安装 Codex CLI。行情刷新仍需要访问腾讯行情接口。

## 5. 文件系统与状态

| 路径 | 内容 | 说明 |
|---|---|---|
| `storage/app.db` | 标的、报告、行情、排名、任务与 AI 审计记录 | 本地运行时事实源 |
| `storage/app.db-wal` / `app.db-shm` | SQLite WAL 状态文件 | 运行时由 SQLite 管理 |
| `storage/common/` | Skill 公共数据缓存 | 可安全重建 |
| `storage/staging/` | 任务隔离目录、Codex 日志和中间产物 | 调试任务时查看 |
| `storage/backups/` | 手动备份 | 可选 |
| `storage/logs/` | 预留日志目录 | 当前主要由终端输出 |

数据库是 Web 查询的运行时事实源。`data/*.json` 是导入、导出和审计格式，不是实时查询数据库。

## 6. 许可证与合规边界

- 本项目仅依据 GNU GPL v3.0（SPDX：`GPL-3.0-only`）授权，不自动适用任何更高版本，完整条款见 [LICENSE](../LICENSE)。
- Vue、FastAPI、SQLAlchemy、Codex CLI 等第三方组件仍分别受其自身许可证约束。
- 本仓库采用 GPL 不改变外部行情数据、研究报告、模型输入输出或第三方 API 的使用条款。
- 使用和二次分发前，应独立审查行情数据再分发权限、模型服务条款以及目标司法辖区的许可要求。
- 可使用 `pnpm licenses list`、`pip-licenses` 或组织内部的 SBOM 工具生成更细的依赖清单，并将其作为发布制品归档。

## 7. 开发检查清单

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

依赖升级、数据库迁移和代码改动应放在同一变更中验证，避免只升级其中一部分。
