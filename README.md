# 衡策：A+H 股公司研究系统

面向 A 股与港股单家公司的可审计研究框架。系统先识别商业模式、价值驱动和主要矛盾，再按公司选择研究周期、关键 KPI、专业角色、可比基准和估值方法。最终输出是一份一体化公司报告，而不是固定研究员流水账或组合仓位建议。

报告重点回答：

- 公司如何赚钱，竞争优势如何转化为利润、ROIC 和自由现金流；
- 当前增长点是什么，增长正在加速、稳定、放缓还是尚无法判断；
- 哪些基本面变化已经被股价计入，哪些仍存在预期差；
- 什么估值方法适合这家公司，动态安全边际应是多少；
- 理想买入、可接受买入、合理持有和估值偏贵/卖出复核价格在哪里；
- 哪些风险会破坏 thesis，下一步应监测什么。

企业质量、增长势头、估值状态和市场计价程度分别判断，不压缩成单一 BUY/SELL 分数。报告不包含目标仓位、调仓比例、组合权重或订单计划。

## 推荐使用方式：直接对话

Codex 技能源码位于 `skills/ah-research-team/`。安装后可输入：

```text
使用 $ah-research-team 全面研究贵州茅台，重点解释增长点、市场已经计价了多少，以及合理的买入和卖出复核区间。

使用 $ah-research-team 研究腾讯控股。不要机械套互联网同业，先判断哪些业务真正可比，并围绕主要矛盾形成一体化报告。
```

对话先调用本地工具准备量价、财务和估值 evidence packet，再查交易所公告、公司 IR 与其他可靠来源。Research Lead 会生成 company-specific research blueprint，动态选择必要研究能力，并把内部争议编辑成一份完整报告。Codex 负责语言模型推理，不需要额外 LLM API Key。

## 当前能力

- 统一 A/H 证券代码：`600519.SH`、`300750.SZ`、`830799.BJ`、`00700.HK`。
- 按消费品牌、数字平台、资本密集制造、金融资产负债表、研发管线等商业类型生成不同研究蓝图。
- 研究角色按问题动态选择，不使用固定 Agent 数量或固定因子权重。
- 同业比较为条件式步骤：只有真正可比且能改变结论时才使用；独特公司可改用自身历史、单位经济、SOTP 或情景估值。
- 将企业质量、增长势头、估值状态和市场计价程度分别建模。
- 安全边际随公司质量、周期性、预测确定性和关键风险变化。
- 缺少正常化盈利、现金流或估值锚时拒绝编造精确价格。
- 离线 Demo、严格 JSON 数据契约与 AkShare A/H 行情/当日聚合财务适配器。
- Markdown/JSON 一体化研究报告；Web 是可选查看器。

AkShare 最新财务与估值接口没有完整原始披露时间，只用于当日研究并标记 `point_in_time=false`。历史研究不会倒灌这些数据。决定商业模式、增长来源和估值区间的关键数字需要回查法披原文或可追溯数据。

## 快速开始

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip setuptools wheel
.venv/bin/python -m pip install -e '.[akshare]'
```

真实数据基线：

```bash
.venv/bin/ashare-research analyze 600519.SH --provider akshare
.venv/bin/ashare-research analyze 00700.HK --provider akshare --json
```

离线验证：

```bash
PYTHONPATH=src python3 -m ashare_research analyze 600519.SH --provider demo
```

使用自己的 point-in-time 数据：

```bash
PYTHONPATH=src python3 -m ashare_research analyze 600519.SH \
  --date 2026-08-18 \
  --data-file examples/research_data.json \
  --save
```

数据契约示例见 [examples/research_data.json](examples/research_data.json)。其中离线情景价值只用于验证价格区间计算，不代表真实估值。

## Web 报告查看器

```bash
cd web
pnpm install
pnpm run dev
```

浏览器访问 `http://localhost:3000`。将 Python 研究结果同步到 Web：

```bash
PYTHONPATH=src python3 -m ashare_research analyze 600519.SH \
  --date 2026-08-18 \
  --web-url http://localhost:3000
```

Web 展示企业质量、估值状态和市场计价程度，不展示组合仓位。

## 独立工程模块

仓库保留 `portfolio.py` 与 `backtest.py` 作为解耦的模拟成交和 walk-forward 回测工具，供工程验证使用。它们不参与公司研究结论，也不进入最终报告。

## 验证

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m unittest discover -s tests -v
cd web && pnpm run build && node --test tests/rendered-html.test.mjs
```

- [系统架构](docs/architecture.md)
- [当前产品范围与数据路线](docs/product_scope.md)

> 本项目仅用于公司研究与工程验证，不构成投资建议。
