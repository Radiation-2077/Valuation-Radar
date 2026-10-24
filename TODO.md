# 估值雷达 TODO：Codex 数据与前端展示契约

> 更新日期：2026-10-24
> 当前结论：Codex 能生成并入库的结构化数据，尚未被后端校验和前端渲染完整消费。
> 当前阶段：先封闭数据契约，再处理动态行情与排名口径，最后补齐可观测性和回归测试。

## 审计基线

- 当前中国平安 Codex revision 2 包含 17 个章节，但 `valuation_scenarios`、`range_position`、`position_tiers`、`premium_donut` 未展示，`return_stack` 为空白图，`risk_cards.severity` 未显示。
- 后端 `validate_card()` 会接受未知 block、空 `expected_return`、空 `position`、非法 path/asset type、缺失风险等级和错误的展示层数值。
- `scorecard.py` 能通过当前 Codex 卡，但仍允许顶层字段与 `presentation` 数值不一致。
- `rank.py` 当前输出 33 个排序单元，Web 数据库排名输出 29 个；旧卡重复参与 skill 排名，Web 只使用最新已发布版本。
- 数据库仍有 `missing` 非空的已发布 Codex 报告参与排名，新候选严格拦截规则没有回溯处理历史数据。

## P0：阻断错误数据进入页面

- [ ] 建立唯一、版本化的数据卡 JSON Schema，覆盖顶层、`markets[]`、`presentation.sections[]` 和所有 block；manifest schema 不能代替数据卡 schema。
- [ ] Codex 输出文件、后端导入和前端 fixture 共用该 Schema，并生成或校验 TypeScript 类型，消除 Python、Markdown、Vue 三套手写契约。
- [ ] 将 `scorecard.py` 或等价的严格校验设为后端强制门槛；校验失败不得写入 `needs_review`，不得只依赖模型在 prompt 中自觉执行。
- [ ] 补齐 canonical block 渲染：`valuation_scenarios`、`range_position`、`position_tiers`、`premium_donut`，并将 `return_stack` 改为读取 `source/value_pct/total_pct`。
- [ ] 将 `risk_cards.severity` 映射为高/中/低及正确颜色；移除对旧版 `level/probability` 的依赖，或提供明确兼容转换。
- [ ] 未知 section、未知 block 和缺失必填字段必须返回可诊断错误；禁止静默跳过、渲染空白图或把缺失数值降级为 0。
- [ ] 校验重复市场、货币、市场代码、block 枚举、百分数字段、有限数值、负回撤、合理区间顺序、仓位分配合计和收益分项闭合。
- [ ] 校验顶层与 `presentation` 同源同值，包括 `fair_mid`、现价、预期收益、最大回撤、目标仓位、仓位档位和市场 verdict，并定义允许的舍入误差。
- [ ] 对现有 Codex 报告执行一次严格重审：隔离 `missing` 非空的已发布记录，重新生成或人工复核后再进入排名。

## P0：统一排名事实源

- [ ] 明确唯一生产排名来源。建议 Web 继续使用数据库排名，并将 `investment-ranking` 定位为离线预览或导出器，避免两份榜单都被称为“前端可直接消费”。
- [ ] 让 `rank.py` 按“标的 × 市场”只选择最新有效数据卡，排除重复日期和旧卡；排名门槛、ETF 分组、是否发布必须与后端一致。
- [ ] 对齐 skill 输出与 `RankingResponse`：字段名、profile 结构、ETF/排除项、计数、`top_three`、`stale_days` 和算法版本必须可机器比对。
- [ ] 增加同一数据快照下的 skill/Web 排名一致性测试，覆盖重复数据卡、A/H 双市场、ETF、排除项和空榜单。

## P1：定义动态行情与展示口径

- [ ] 明确静态估值字段与实时行情字段的边界：`analysis_price`、`current_price`、`card_safety_margin_pct`、`effective_safety_margin_pct` 不得互相覆盖。
- [ ] 最新行情变化后，要么原子重算所有受价格影响的收益、情景和档位，要么在页面明确区分“分析日口径”和“当前行情口径”。
- [ ] 排名使用最新行情或宏观数据时，详情页必须返回同一快照；禁止排名分已重算但页面仍展示旧 `macro` 或旧预期收益。
- [ ] 定义 `gauges.*.value` 的精确语义和范围。明确哪些项是原始指标、哪些是 0–100 吸引力分，并校验 `display_value` 与 `value` 一致。
- [ ] 定义负安全边际在仪表盘中的展示方式，避免文字为负值但进度弧按 0 显示。
- [ ] 正式定义 `confidence`、`verdict`、`asset_type`、`path`、`currency`、`market`、`severity` 和 `tone` 的枚举；评分只接受明确枚举，避免 `"low"`、`"较低"` 等值绕过扣分。
- [ ] 为 verdict 提供语义色，禁止所有买入、观望、减仓结论都显示为绿色成功标签。
- [ ] 校验 `cycle_position`、`gauges.certainty`、`quality.score` 和仓位字段的范围及百分比基准。

## P1：清理前端隐式规则

- [ ] section 和列表项使用稳定 `id`/复合 key，不依赖可能重复的中文标题或 item label。
- [ ] 移除或正式约定基于“仓位”“关键结论”“决策仪表盘”“A 股估值”等标题子串的布局和过滤启发式。
- [ ] 前端开发服务器改为局域网监听后，核对 API 代理、跨设备访问和 CORS/安全边界，补充局域网访问说明与回归检查。
- [ ] 行情表的新鲜度标记统一使用 API 返回的 `stale_after_days`，不要在页面另写固定的 7 天阈值。
- [ ] 明确市场筛选中 `CN` ETF 的展示规则，避免 ETF 在独立表中出现却无法按市场筛选。

## P1：回归测试与可观测性

- [ ] 以真实 schema 1.1 A+H 数据卡建立前端 fixture，逐项断言仪表盘、质量 grid、情景/区间、仓位档位、收益拆解、溢价环图、风险等级、来源和免责声明均可见。
- [ ] 增加反向 E2E：未知 block、错误字段名、空收益、冲突中枢和非法枚举必须明确报错，不能静默消失。
- [ ] 增加顶层字段与展示层字段一致性测试，以及排名阈值、最新卡去重、行情/宏观快照一致性测试。
- [ ] 在任务中心和 Debug 面板保存并展示 schema 版本、校验器版本、卡片哈希、使用的行情/宏观快照及拒绝原因。
- [ ] 修正当前依赖 `../data` 的测试路径探测，确保真实数据存在时 import、排名和 skill parity 测试不会无提示跳过。

## 验收标准

- [ ] 任意通过后端校验的 Codex 卡，都能被前端完整渲染；不存在声明了 block 却静默丢失的情况。
- [ ] 任意非法、冲突或不完整的数据卡都会在写库和发布前失败，并给出具体字段路径。
- [ ] 同一份数据快照下，skill 排名与 Web 排名的主榜、ETF、排除项、顺序和分数一致。
- [ ] 当前价格刷新后，页面不会把新现价与旧收益、旧情景或旧仓位无提示地混在一起。
- [ ] 当前数据库中不存在带 `missing` 且仍参与主榜的 Codex 发布记录。
- [ ] 真实 schema 1.1 数据卡的详情页 E2E 与严格拒绝用例均通过。
