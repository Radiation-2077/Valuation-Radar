# 估值雷达

本机优先的估值分析工作台。项目把现有估值数据卡、三套风险偏好排名和估值报告升级为可查询、可追溯、按交易日更新的 Web 应用。

## 界面预览

### 性价比排名

![性价比排名首页](docs/screenshots/dashboard.png)

### 同页估值详情

![标的估值详情](docs/screenshots/valuation-detail.png)

### 数据更新与运行状态

![数据更新与运行状态](docs/screenshots/updates.png)

### 候选估值预览

![候选估值预览](docs/screenshots/review-preview.png)

## 已实现

- Vue 3 排名首页：稳健保守 / 均衡 / 进取三套榜单、Top 3、象限图、筛选和完整排名。
- 同页完整估值详情：点击排名后在当前页面展开，包含合理区间、当前安全边际、收益拆解、四维评分、仓位、风险和 A/H 对照。
- SQLite 数据层：历史估值版本、市场快照、行情、宏观数据、排名快照、任务和 AI 运行记录。
- 收盘后自动更新：交易日历、可配置开关/频率/时间、行情抓取、任务幂等和排名重算。
- Codex 持久会话：首次运行保存 `thread_id`，暂停、中断或服务重启后通过 `codex exec resume` 续接原会话和工作目录，避免重复取证与计算。
- 任务生命周期：估值任务支持暂停、恢复、单任务删除和累计执行时间；删除运行中任务时会先终止 Codex 进程组，再清理任务记录和暂存目录。
- Codex 估值闭环：隔离暂存目录调用 `value-investing` skill，Python 校验后进入人工复核队列；同一任务的多轮执行在 Debug 中合并为一个逻辑会话，同时保留逐次运行的审计明细。
- 候选复核：待复核卡片先进入完整估值预览，批准、拒绝按钮固定在预览底部；已拒绝候选支持预览、重新估值和永久删除。
- ETF 数据约束：校验前十大成分权重、代表 PB 的调和平均、净值与价格同步日期、折溢价率及章节展示契约，减少不可审计的 ETF 估值结果。
- 手动添加标的：主页可按名称创建估值任务，证券代码可选；未提供代码时由 Codex 检索市场，A/H 两地上市默认同时调研。
- 标的生命周期：标的库支持移出榜单、恢复和输入名称确认后的彻底删除；归档保留全部估值历史，彻底删除同步清理关联任务与暂存目录。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Vue Router、Naive UI 默认暗色主题、TanStack Vue Query、ECharts
- 后端：FastAPI、Pydantic v2、SQLAlchemy 2、Alembic
- 数据库：SQLite（WAL）
- 调度：独立 scheduler + 单实例 worker + 数据库任务表
- 模型：Codex CLI `exec`，工作目录沙箱，不直接写生产数据库

架构细节见 [docs/architecture.md](docs/architecture.md)，展示与数据卡契约见
[docs/PRESENTATION_CONTRACT.md](docs/PRESENTATION_CONTRACT.md)，完整阶段计划见
[docs/DEVELOPMENT_PLAN.md](docs/DEVELOPMENT_PLAN.md)。

视觉样式统一由 `apps/web/src/theme.ts` 和 `apps/web/src/styles/` 管理：主题 token、页面布局和少量品牌组件样式分别集中，不在页面组件中散落自定义视觉规则。

## 首次启动

前置要求：Python 3.12、Node.js、pnpm、已登录的 Codex CLI。

```bash
cd /home/canon/finacial/valuation-web
make setup
pnpm dev
```

访问：

- Web：<http://127.0.0.1:5173>
- API：<http://127.0.0.1:8000>
- OpenAPI：<http://127.0.0.1:8000/docs>

`make setup` 会创建虚拟环境、安装依赖、迁移数据库，并导入上级目录中的 21 张结构化数据卡。新流程不为单个标的保存 HTML。

## 常用命令

```bash
pnpm dev             # API、Web、worker、scheduler
pnpm test            # 后端与前端单元测试
pnpm test:e2e        # Edge 桌面/手机端到端测试
pnpm lint            # Ruff + ESLint
pnpm typecheck       # mypy + vue-tsc
pnpm build           # 生产前端构建
pnpm db:migrate      # 执行 Alembic 迁移
pnpm import:legacy   # 重复导入是幂等的
```

## 数据流

```text
data/*.json
        ↓ 导入与校验
SQLite 历史估值版本
        ↓ 四维评分
三套排名快照

交易日收盘后 → scheduler → job_runs → worker
                                  ├─ 行情/宏观写入 → 排名重算
                                  ├─ Codex 持久会话 ─┬─ 暂停 / 恢复
                                  │                   ├─ 中断后续接
                                  │                   └─ 终止并删除
                                  └─ 候选估值校验 → 预览复核
                                                       ├─ 批准 → 发布并重算排名
                                                       └─ 拒绝 → 保留或删除
```

最新行情只改变“当前安全边际”和排名，不改写历史合理中枢。Codex 结果批准前不会进入当前排名。暂停、中断和恢复不会重置累计执行时间；只有当前工作目录或持久会话不可用时，才会回退为新的 Codex 会话。

## 数据与安全

- Web 开发服务器监听 `0.0.0.0`，允许同一局域网内访问；API 仍仅监听 `127.0.0.1`，浏览器请求通过 Vite 的 `/api` 代理转发。
- 数据库、日志、归档和暂存目录均被 Git 忽略。
- 模型在 `storage/staging/` 隔离目录执行，使用 `workspace-write` 沙箱。
- Codex 会话由本机 Codex CLI 持久化；任务删除会终止对应进程组并清理任务暂存目录。
- 新估值的必需数据缺失时立即终止，不生成或发布候选卡；历史卡只做只读兼容。
- 所有分析结果仅用于研究，不构成投资建议。
