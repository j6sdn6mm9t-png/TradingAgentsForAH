# A+H 股公司研究系统架构

## 1. 设计目标

系统将 Codex 对话作为研究编排层，将 Python 包作为证据、时点校验、公司研究状态和报告渲染层。主流程围绕公司及其估值，不围绕组合决策。

| 层 | 职责 | 关键约束 |
|---|---|---|
| Data Provider | 行情、财务、估值上下文与证据 | 不做投资结论，不把聚合源冒充法披 |
| Research Planner | 识别商业类型、主要矛盾、周期、KPI、角色与可比策略 | 不使用固定 Agent 名单或固定因子权重 |
| Adaptive Researchers | 商业模式、质量、增长、估值、预期及公司特定专题 | 只回答本次研究蓝图中的问题 |
| Independent Challenge | 攻击增长质量、会计、治理、周期和估值假设 | 不按人数投票或重复辩论增加置信度 |
| Valuation | 公司适用方法、情景价值、动态安全边际和价格区间 | 输入不足时拒绝虚假精确 |
| Research Lead / Report | 裁决证据与分歧，输出一体化公司报告 | 不展示逐角色流水账，不输出组合仓位 |

## 2. 领域状态

`ResearchState` 分开保存：

- `ResearchBlueprint`：公司 archetype、研究周期、主要问题、关键 KPI、角色和可比策略；
- `AnalystReport[]`：内部结论、反证、未知量与证据引用；
- `ValuationContext`：外部提供且可审计的 bull/base/bear 情景价值；
- `ValuationAssessment`：估值方法、动态安全边际、市场计价状态和价格区间；
- `ResearchSynthesis`：企业质量、增长势头、主要矛盾、风险、证伪和最终公司结论。

企业质量、增长势头、估值状态和市场计价程度是独立维度。系统不再用 `strong_buy/buy/hold/reduce/sell` 同时代表公司好坏与价格高低。

## 3. 时间与证据语义

- `as_of`：研究截止时点，只允许使用当时已经可见的信息。
- `published_at`：材料公开时间，必须不晚于研究日。
- `observed_at`：系统实际获取时间，未来时间会被拒绝。
- `period_end`：财务所属期间，不能代替披露日期。
- `point_in_time=false`：聚合接口缺少可靠披露时间，只能在当日研究中作为线索。

关键数字需要 claim-level evidence。最终报告必须区分事实、分析推断和情景假设。

## 4. 自适应研究

`ResearchPlanner` 根据行业与已有证据生成初始蓝图。消费品牌、数字平台、资本密集制造、金融机构、研发管线和未知公司会得到不同研究周期、KPI、专题角色与可比策略。

代码中的规则只提供离线 deterministic baseline。真实研究由 Codex 读取分部披露后修订蓝图，可合并、添加或删除角色。新增角色不会进入固定权重表，因为系统不存在统一总分。

同业比较状态默认为条件式：只有业务结构、客户、盈利驱动、资本强度、增长阶段和风险暴露足够接近时才使用。公司独特时改用自身历史、单位经济、SOTP、DCF 或里程碑情景。

## 5. 估值与价格纪律

`MarketDataProvider.get_valuation_context()` 可以返回已被证据支持的 bull/base/bear 情景价值。AkShare 不提供可审计的前瞻情景，因此适配器返回空上下文；Demo 与 JSON 示例只用于验证数据契约。

动态安全边际由企业质量、周期性、预测确定性、杠杆、数据时效和治理风险共同决定。只有完整情景价值存在时才生成理想买入、可接受买入、合理持有和卖出复核区间。市场计价判断还需要 reverse valuation、一致预期修正与历史事件反应；仅靠价格区间得到的状态必须标明局限。

## 6. 数据适配契约

```python
class MarketDataProvider(Protocol):
    def get_snapshot(self, security, as_of): ...
    def get_evidence(self, security, as_of): ...
    def get_valuation_context(self, security, as_of): ...
```

生产适配器必须固定单位和空值语义，保留原始来源、披露时点、报告期、币种和口径。财务时间序列、分部数据、有效 peer set 和一致预期属于下一步重点扩展。

## 7. 独立工程工具

`PaperPortfolio` 与 `BacktestEngine` 仍可用于模拟成交和 walk-forward 工程验证，但与公司研究主流程解耦，不影响 `ResearchState`、估值结论或最终报告。
