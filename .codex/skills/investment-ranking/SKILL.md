---
name: investment-ranking
description: 把已估值过的个股与 ETF 放到同一把尺子上做风险调整后的性价比排序，输出可审计、可与 Web 排名对照的结构化 JSON（稳健 / 均衡 / 进取三套风险偏好）。当用户说「性价比排序 / 哪个更值得买 / 横向对比 / 这几个选哪个 / 排个序 / 在持仓里挑」，或给出一组股票、ETF 想比较谁当前更值得买时使用。依赖 value-investing schema 1.2 数据卡，不重新估值。
metadata:
  short-description: 投资性价比排序与结构化榜单生成
---

# 投资性价比排序

读取 `data/` 中的 value-investing schema 1.2 数据卡，按标的保留最新卡，过质地与数据门槛，计算四维分和三套风险偏好排名，输出 JSON。Web 运行时的正式排名仍以数据库 `RankingService` 为准，本脚本用于离线复核与结果对照。

**本 skill 不重新估值，也不生成 HTML。**

## 硬性规则

1. **输出 JSON。** 默认文件名 `投资性价比排序_{YYYY-MM-DD}.json`。
2. **只用脚本打分。** 运行 `python3 scripts/rank.py`；脚本是评分口径的唯一事实来源。
3. **三套风险偏好同时输出。** 固定键为 `conservative` / `balanced` / `aggressive`，展示名称分别为稳健保守、均衡、进取。
4. **输出结构与 value-investing 的排序单元一致。** 一条记录是「标的 × 市场」；A/H 两地分别参与排序。
5. **数据完整性先于排名。** 任一数据卡无法解析、schema 校验失败或必需字段缺失时立即抛错并停止，不生成榜单；只有数据完整的卡才允许因质地门槛进入 `excluded`。
6. **无需生成视觉代码。** 不在 JSON 中输出 class、CSS、HTML、SVG 或组件名。图表所需的坐标、分项分、风险标签必须保存为数字和数组。
7. **不使用池内归一化。** 保持绝对锚定，避免小样本把最差标的抬成 0 分、最好标的抬成 100 分。
8. **不把估值收益算两次。** 安全边际维度负责估值修复；基础收益维度只取股息、增长和汇率。
9. **标注时效。** 每条记录保留 `analysis_date` 与 `stale_days`；前端可据 `stale_days > 7` 标记偏旧。
10. **写完后自检 JSON。** 确认三套 profiles 均存在、排名连续、排除项带原因、无 NaN/Infinity。

## 工作流程

### 1. 盘点数据卡

```bash
python3 /home/canon/.codex/skills/value-investing/scripts/scorecard.py list --dir data
```

确认分析日期、市场代码和数据完整性；任何必需字段缺失立即终止。只使用 schema 1.2 卡；同一标的有多张卡时，`rank.py` 自动选择 `analysis_date + generated_at` 最新的一张。

### 2. 补齐估值

缺卡或关键字段缺失时，用 value-investing skill 重新估值并生成 schema 1.2 数据卡。不要在排序文件中手填上游缺失值。

### 3. 生成排序 JSON

```bash
# 打印完整 JSON，便于检查
python3 scripts/rank.py --data-dir data --json

# 写入默认文件
python3 scripts/rank.py --data-dir data

# 指定输出
python3 scripts/rank.py --data-dir data --out 投资性价比排序_2026-10-22.json
```

### 4. 复核结论

- 是否有“高分但一眼不该买”的记录，例如收益高度依赖估值回归、周期位置过高。
- 同一公司的 A/H 是否同时靠前，需要提示经营敞口相关性；本 skill 不估计仓位大小。
- 三套权重下名次变化是否符合稳健 / 均衡 / 进取的偏好。
- `excluded` 是否只包含数据完整但质地不达标的单元，并给出原因。

## 输出 JSON 契约

```json
{
  "schema_version": "1.0",
  "generated_at": "2026-10-22T18:00:00+08:00",
  "as_of": "2026-10-22",
  "default_profile": "balanced",
  "source": {
    "data_dir": "data",
    "cards": 12,
    "ranking_units": 15
  },
  "summary": {
    "covered_instruments": 12,
    "main_board_units": 13,
    "etf_units": 2,
    "buy_candidates": 5,
    "excluded_units": 1
  },
  "profiles": {
    "conservative": {
      "label": "稳健保守",
      "description": "风险与确定性优先",
      "weights": {"margin":0.25,"base":0.15,"risk":0.30,"stability":0.30},
      "items": []
    },
    "balanced": {
      "label": "均衡",
      "description": "默认基准",
      "weights": {"margin":0.30,"base":0.25,"risk":0.20,"stability":0.25},
      "items": []
    },
    "aggressive": {
      "label": "进取",
      "description": "以预期收益为主",
      "weights": {"margin":0.25,"base":0.40,"risk":0.15,"stability":0.20},
      "items": []
    }
  },
  "etfs": [],
  "excluded": [],
  "notes": []
}
```

每个榜单 item 至少包含：

```json
{
  "rank": 1,
  "band": "S",
  "score": 81.7,
  "name": "宁德时代",
  "market": "A",
  "code": "300750.SZ",
  "currency": "CNY",
  "asset_type": "stock",
  "path": "cyclical",
  "industry": "动力电池",
  "analysis_date": "2026-10-21",
  "stale_days": 1,
  "price": 232.74,
  "fair_mid": 360,
  "safety_margin_pct": 35.4,
  "expected_return_pct": 27.9,
  "base_income_pct": 12.3,
  "max_drawdown_pct": -31.3,
  "verdict": "分批买入",
  "thesis": "一句话逻辑",
  "confidence": "中",
  "scores": {
    "safety_margin": 91,
    "base_income": 78,
    "downside": 62,
    "stability": 76
  },
  "risk_adjusted_ratio": 0.84,
  "valuation_reliance": 0.56,
  "risk_flags": ["收益依赖估值回归"]
}
```

`excluded.item` 使用相同主体字段，并额外提供 `excluded_reasons[]`。

## 四维打分

| 维度 | 输入 | 稳健 | 均衡 | 进取 |
|:---|:---|:---:|:---:|:---:|
| 安全边际 | `safety_margin_pct` | 0.25 | 0.30 | 0.25 |
| 基础收益 | `dividend + growth + fx − rf` | 0.15 | 0.25 | 0.40 |
| 抗跌性 | `abs(max_drawdown_pct)` + 周期位置修正 | 0.30 | 0.20 | 0.15 |
| 稳定性 | 质地分 + 确定性 + 路径/星级扣分 | 0.30 | 0.25 | 0.20 |

完整锚点与规则见 [references/评分口径.md](references/评分口径.md)。

## 与 value-investing 的关系

```text
value-investing   : 标的 -> 估值 -> data/{标的名}_{date}.json
investment-ranking: data/*.json -> 四维打分 -> 投资性价比排序_{date}.json
```

两个 skill 通过 value-investing 的 `card-v1.2.schema.json` 解耦。修改字段、枚举或 section 契约时，必须同步 `scripts/rank.py` 与 value-investing 的 `scripts/scorecard.py`。

## 参考文档

- [references/评分口径.md](references/评分口径.md) — 锚点、权重、去重规则与局限
- value-investing 的 `references/数据卡规范.md` — 上游数据卡 schema
- value-investing 的 `references/报告区块规范.md` — presentation 控件语义
