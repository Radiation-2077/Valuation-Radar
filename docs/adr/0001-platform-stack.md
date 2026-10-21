# ADR 0001：采用 Vue 3、FastAPI 与 SQLite

- 状态：已接受
- 日期：2026-10-21

## 背景

应用以本机单用户为主，需要动态排名、估值详情、后台抓取、定时任务和 Codex 估值编排。现有事实数据为 `data/*.json`，现有分析产物为离线 HTML。

## 决策

1. 前端使用 Vue 3、TypeScript、Vite 和 Vue Router。
2. 数据查询使用 TanStack Vue Query，复杂图表使用 Apache ECharts。
3. 后端使用 FastAPI、Pydantic v2、SQLAlchemy 2.0 和 Alembic。
4. 首版数据库使用启用 WAL 的 SQLite。
5. 数据抓取、任务调度和 Codex 执行分别运行在 worker/scheduler 进程中，不阻塞 API。
6. JSON 数据卡和 HTML 报告保留为导入、导出和审计格式；应用查询以数据库为准。

## 后果

- 单机部署无需额外数据库或消息队列。
- SQLite 写入并发有限，因此任务 worker 首版限制为一个。
- 后续需要多用户或局域网部署时可迁移 PostgreSQL，API 和领域层无需重写。
- 模型执行必须隔离，不能直接修改运行时数据库或当前发布版本。
