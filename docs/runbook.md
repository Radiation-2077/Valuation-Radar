# 开发运维

本文记录本地开发时的启动、状态检查和常见故障处理。首次安装见 [Quick Start](QUICKSTART.md)，依赖版本见 [依赖说明](DEPENDENCIES.md)，Codex Skill 见 [Codex Skill 安装](CODEX_SKILLS.md)。

## 启动

从仓库根目录启动全部开发进程：

```bash
pnpm dev
```

如依赖或数据库尚未初始化：

```bash
pnpm run bootstrap
pnpm dev
```

需要查看单个进程日志时，分别运行：

```bash
pnpm dev:api
pnpm dev:web
pnpm dev:worker
pnpm dev:scheduler
```

## 检查状态

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/schedule
curl -s http://127.0.0.1:8000/api/v1/jobs
curl -s http://127.0.0.1:8000/api/v1/reviews
```

Web 开发地址是 <http://127.0.0.1:5173>，API 文档是 <http://127.0.0.1:8000/docs>。

## 手动刷新行情

在 Web 的“更新中心”点击“立即刷新行情”，或调用：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: manual-$(date +%s)" \
  -d '{"job_type":"market_refresh","scope":"all"}'
```

刷新任务依赖 worker。只启动 `pnpm dev:web` 时任务会一直排队。

## Codex 重新估值

在估值详情点击“请求 Codex 重新估值”。任务完成后候选版本出现在“更新中心 → 待复核 Codex 估值”。

检查 CLI、登录态和 Skill：

```bash
codex --version
codex login status
test -f "$HOME/.codex/skills/value-investing/SKILL.md"
test -f "$HOME/.codex/skills/investment-ranking/SKILL.md"
```

任务日志位于：

```text
storage/staging/job-{id}/{标的名}/codex.stdout.jsonl
storage/staging/job-{id}/{标的名}/codex.stderr.log
```

## 数据库迁移

```bash
pnpm db:migrate
```

需要手工备份本地数据库时：

```bash
mkdir -p storage/backups
sqlite3 storage/app.db ".backup storage/backups/app-$(date +%Y%m%d-%H%M%S).db"
```

这一命令需要 `sqlite3` CLI；日常安装不要求该工具。

## 开发检查

```bash
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

端到端测试：

```bash
pnpm test:e2e
```

## 常见故障

| 现象 | 检查 |
|---|---|
| 任务一直排队 | worker 是否运行，查看 `jobs` 状态 |
| 页面显示旧排名 | 检查任务失败原因与腾讯行情源连通性 |
| Codex 退出码非零 | 查看 `codex.stderr.log`、`ai_runs` 和 `codex login status` |
| Codex 提示找不到 Skill | 按 [Codex Skill 安装](CODEX_SKILLS.md) 检查全局链接 |
| API 不可达 | 检查 `127.0.0.1:8000/health` 和 `pnpm dev:api` 日志 |
| 页面不可达 | 检查 `127.0.0.1:5173` 和 `pnpm dev:web` 日志 |
| 候选未进入排名 | 是否仍在待复核队列，是否已批准 |
| 休市日未运行 | 调度配置中的交易日历与时区 |
