# 本地运维手册

## 启动

```bash
cd /home/canon/finacial/valuation-web
pnpm dev
```

如依赖或数据库尚未初始化：

```bash
make setup
```

## 检查状态

```bash
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/api/v1/schedule
curl -s http://127.0.0.1:8000/api/v1/jobs
curl -s http://127.0.0.1:8000/api/v1/reviews
```

## 手动刷新行情

在 Web 的“更新中心”点击“立即刷新行情”，或调用：

```bash
curl -X POST http://127.0.0.1:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: manual-$(date +%s)" \
  -d '{"job_type":"market_refresh","scope":"all"}'
```

## Codex 重新估值

在估值详情点击“请求 Codex 重新估值”。任务完成后候选版本出现在“更新中心 → 待复核 Codex 估值”。

检查 Codex CLI：

```bash
codex --version
codex login status
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

迁移前建议备份：

```bash
sqlite3 storage/app.db ".backup storage/backups/app-$(date +%Y%m%d-%H%M%S).db"
```

## 常见故障

| 现象 | 检查 |
|---|---|
| 任务一直排队 | worker 是否启动，查看 `jobs` 状态 |
| 页面显示旧排名 | 检查任务失败原因与行情源健康 |
| Codex 退出码非零 | 查看 `codex.stderr.log` 和 `ai_runs` |
| 候选未进入排名 | 是否仍在待复核队列，是否已批准 |
| 休市日未运行 | 调度配置中的交易日历与时区 |
