# 系统架构

## 运行单元

| 进程 | 职责 |
|---|---|
| `web` | Vue 3 + Naive UI SPA，查询排名、同页详情、调度与复核状态 |
| `api` | FastAPI，只做查询和任务投递 |
| `scheduler` | 按交易日历检查计划并创建幂等任务 |
| `worker` | 执行行情刷新或 Codex 估值任务 |

开发环境由根目录 `pnpm dev` 同时启动四个进程。API 默认 `127.0.0.1:8000`，前端默认 `127.0.0.1:5173`。

## 数据边界

```text
只读输入
  ../data/*.json
  ../common/*.json

运行时事实源
  storage/app.db

不可变产物
  storage/staging/
```

数据库是 Web 查询事实源，数据卡是导入、导出和审计格式。前端完整详情直接从数据库动态渲染，不保存单标的 HTML。

## 关键表

| 表 | 说明 |
|---|---|
| `instruments` / `listings` | 标的与“标的 × 市场”上市单元 |
| `valuation_reports` | 不可变估值报告版本及发布状态 |
| `valuation_markets` | 分市场合理区间、收益、回撤与仓位 |
| `quote_observations` | 行情快照 |
| `macro_observations` | 利率、汇率和 AH 溢价等事实 |
| `ranking_runs` / `ranking_entries` | 每轮排名及四维评分快照 |
| `schedule_settings` | 自动更新计划 |
| `job_runs` | 任务状态、幂等键和结构化结果 |
| `ai_runs` | Codex CLI 版本、日志和候选产物记录 |

## 排名更新

1. 选每个标的最新已发布估值版本。
2. 用最新行情计算当前安全边际。
3. 用最新宏观数据替代上一轮无风险利率。
4. 按现有 `investment-ranking` 口径计算三套排名。
5. 固化 `ranking_run`，不修改历史估值报告。

## Codex 估值

1. API 创建 `valuation_refresh` 任务。
2. worker 建立 `storage/staging/job-{id}/`。
3. 复制 `common/`，写入上一版数据卡、最新行情证据和 prompt。
4. `codex exec` 在隔离目录运行，提示其调用 `value-investing` skill。
5. Python 校验进程退出码、数据卡 schema、日期与标的名。
6. 候选报告以 `needs_review` 状态写入数据库。
7. 人工批准后才变为 `published`，随后重算排名。

## 失败策略

- 行情源部分失败：任务标记 `partial`，已取得的行情仍可入库。
- 整轮没有有效行情：任务失败，旧排名保持可读。
- Codex 超时、退出异常或产物非法：候选被拒绝，不进入排名。
- 同步/调度重复触发：数据库幂等键阻止重复任务。
