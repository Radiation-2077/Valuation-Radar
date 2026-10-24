# 估值报告展示契约

> 状态：schema 1.2 已接入 Demo、后端导入、详情渲染和两个 Codex skill；TypeScript 类型仍为手写
> Schema：[.codex/skills/value-investing/references/card-v1.2.schema.json](../.codex/skills/value-investing/references/card-v1.2.schema.json)
> 示例：[schemas/value-investing/examples/card-v1.2.example.json](../schemas/value-investing/examples/card-v1.2.example.json)
> 执行校验：[apps/api/app/services/card_contract.py](../apps/api/app/services/card_contract.py)

## 目标

数据卡同时服务排名、详情页和质量审计。不同估值路径可以有不同分析模块，但页面结构、字段单位和渲染语义必须稳定。

本契约采用三层模型：

| 层级 | 固定程度 | 内容 |
|---|---|---|
| 页面壳层 | 固定 | section role、block 类型、数值单位、空值和响应式策略 |
| 估值模块 | 注册式可变 | 金融、周期、稳定增长和 ETF 的专用分析模块 |
| 自然语言 | 自由 | 标题、段落、评价、风险传导和来源说明 |

模型可以决定使用哪些已注册模块，但不能发明 section role、block 类型、表格样式或组件名称。

## Section 角色

页面布局只读取 `role`，不读取中文标题：

```json
{
  "id": "valuation-a",
  "role": "valuation",
  "title": "A 股估值",
  "market": "A",
  "blocks": []
}
```

固定 role：

| role | 用途 |
|---|---|
| `dashboard` | 只放四个核心指标仪表盘，不混入正文、KPI 卡片或本章小结 |
| `quality` | 质地与门槛 |
| `cycle` | 产业与经济周期 |
| `model_analysis` | 路径专用分析模块 |
| `cross_market` | A/H 结构性溢价分解 |
| `valuation` | 合理区间与估值情景 |
| `position` | 仓位与交易纪律 |
| `expected_return` | 收益拆解 |
| `risks` | 风险与压力情景 |
| `conclusion` | 操作结论 |
| `sources` | 数据来源与口径 |
| `disclaimer` | 免责声明 |

section 顺序由数组顺序决定。`id` 必须唯一，标题只表达章节功能，例如“估值”“仓位管理”“溢价分析”，不得写 A 股、H 股或 A/H；市场一律由 `market` 字段和页面顶部市场标签表达。`model_analysis` 必须同时提供 `module`；其他 role 不允许携带 `module`。

`dashboard` 必须只有一个 `gauges` block，固定展示安全边际、估值历史分位、股息率吸引力和确定性四个读数。详细解释放在后续章节，避免首个决策区域出现信息重复。

## 受控估值模块

模块定义放在数据卡顶层 `model_modules[]`，并对应 `role: "model_analysis"` 的章节。

| 路径 | 允许模块 |
|---|---|
| `stable` | `gordon_reverse`、`peg`、`dividend_sustainability`、`dividend_yield` |
| `cyclical` | `normalized_earnings`、`cycle_position`、`pb_roe` |
| `financial` | `pb_roe`、`pev_sensitivity`、`nbv_quality`、`solvency` |
| `etf` | `index_percentile`、`tracking_quality`、`dividend_yield` |

JSON Schema 负责校验模块名称和结构。后续语义校验器负责确认模块是否属于当前 `path`、A/H 分市场要求是否满足，以及模块数值是否与 `markets[]` 一致。

新增模块必须同时提交：

1. 模块枚举和字段 Schema。
2. 前端 canonical 渲染映射。
3. 至少一个真实或结构 fixture。
4. 桌面与移动端回归测试。

## 固定 Block

schema 1.2 只允许以下 canonical block：

```text
heading
paragraph
callout
bullets
table
formula
grid
scores
metric_cards
gauges
industry_lifecycle
industry_cycle
valuation_scenarios
range_position
position_tiers
return_stack
premium_donut
risk_cards
```

旧版 `scenario_bars`、`range_bar`、`steps`、`donut`、`position_block`、`scale` 和 `group` 不进入新卡。历史 schema 1.0/1.1 由只读适配器转换。

未知 block 必须校验失败，不能静默跳过或渲染空白画布。

## 表格契约

表格列不再由模型指定宽度，而是声明语义角色：

```json
{
  "type": "table",
  "variant": "comparison",
  "columns": [
    {"key": "metric", "label": "维度", "role": "label"},
    {"key": "value", "label": "结果", "role": "value"},
    {"key": "comment", "label": "评价", "role": "note"}
  ],
  "rows": [
    {
      "metric": "净现金 / 市值",
      "value": "12.4%",
      "comment": "安全边际较充足"
    }
  ]
}
```

允许的 `role`：

- `label`：项目名，固定较窄列。
- `value`：短数值或结果，数字列稳定对齐。
- `assessment`：简短判断。
- `action`：操作条件。
- `note`：长说明，使用剩余宽度并允许折叠。
- `date`：日期。
- `metric`：指标名或倍数。
- `scenario`：情景名。
- `unit`：单位。
- `status`：状态标签。

前端负责：

- 使用 `table-layout: fixed` 和语义列宽，不使用内容长度反推列宽。
- Grid/Flex 子项设置 `min-width: 0`。
- 长文本使用 `overflow-wrap: anywhere`。
- `note` 单元格最多显示三行，并提供展开入口。
- 移动端把多列长文本表转换为纵向键值卡；数值矩阵允许横向滚动。
- 不静默截断关键内容。

模型只需要把长文本放进 `note`，不需要也不允许输出列宽、CSS、HTML 或行数限制。

## 数值与时间

- 所有百分比字段使用数值，例如 `4.5` 表示 4.5%。
- `allocation_pct` 只表示计划买入内部的分批比例，四档合计 100，不表示资产占比。
- `max_drawdown_pct` 必须小于等于 0。
- `verdict` 和 `confidence` 使用稳定 code 加显示 label，评分逻辑只读取 code。
- `gauges[].kind` 明确仪表盘刻度语义；`value` 是原始值，`display_value` 只负责显示。
- 静态估值和当前行情必须是不同字段。`presentation.current_price` 表示分析日口径，页面实时行情另行提供。

## 版本与兼容

- 新 Codex 卡片只允许写 `schema_version: "1.2"`。
- `presentation.schema_version` 必须同为 `1.2`。
- `missing` 必须为空；必需数据缺失时任务失败，不生成新卡。
- schema 1.0/1.1 只用于历史读取，不接收新候选。
- 任何破坏性字段变化都提升小版本，不静默改变现有字段语义。

## 后续语义校验

JSON Schema 不能完整表达以下约束，后端仍需独立校验：

- 同一市场代码不得重复。
- `fair_low <= fair_mid <= fair_high`。
- 四档建仓比例合计 100，并依次满足 `valuation → evidence → stabilization → catalyst/reserve`。
- 收益分项合计与 `total` 一致。
- 溢价 `share_pct` 合计 100。
- 质量 grid 固定五行并与评分逐行对应；右侧表格只允许“结果 / 评价”两列，不得重复左侧已有的维度名。
- `cycle` 章节第一项必须是 `industry_lifecycle`；`path: "cyclical"` 时第二项必须是 `industry_cycle`，其 `position/phase/direction` 必须与顶层周期位置和固定阶段映射同步。
- `model_analysis` 与 `valuation` 必须包含核心估值公式，`cross_market` 可选；质量、产业周期、仓位、预期收益章节不得出现公式卡。每个公式分别提供符号式 `latex`、数字代入式 `substitution` 和自然语言 `explanation`。
- `model_modules` 与当前 `path` 匹配。
- A+H 必需 section、market 和顺序满足契约。
- `markets[]` 与 `presentation` 的核心数值同源同值。
- 每个业务 section 最后一项为 `summary: true` 的 callout。

当前 `card_contract.py` 已覆盖上述约束，并在测试中运行金融 A/H、稳定增长、周期和 ETF 四类 fixture。新 Codex 候选只接受 1.2；1.0/1.1 仅用于历史读取。
