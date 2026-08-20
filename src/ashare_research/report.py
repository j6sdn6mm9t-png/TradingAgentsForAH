"""Auditable integrated company-research Markdown and JSON renderers."""

import json
from pathlib import Path
from typing import Dict, Optional

from .domain import (
    CompanyQuality,
    GrowthMomentum,
    PricingStatus,
    ResearchState,
    ValuationView,
)
from .market import Exchange


_QUALITY_LABELS: Dict[CompanyQuality, str] = {
    CompanyQuality.EXCELLENT: "优秀",
    CompanyQuality.GOOD: "良好",
    CompanyQuality.MIXED: "一般",
    CompanyQuality.WEAK: "较弱",
    CompanyQuality.INSUFFICIENT: "证据不足",
}
_GROWTH_LABELS: Dict[GrowthMomentum, str] = {
    GrowthMomentum.ACCELERATING: "加速",
    GrowthMomentum.STEADY: "稳定",
    GrowthMomentum.SLOWING: "放缓",
    GrowthMomentum.REVERSING: "反转/收缩",
    GrowthMomentum.UNCERTAIN: "无法判断斜率",
}
_VALUATION_LABELS: Dict[ValuationView, str] = {
    ValuationView.ATTRACTIVE: "有吸引力",
    ValuationView.REASONABLE: "合理",
    ValuationView.DEMANDING: "偏贵",
    ValuationView.EXCESSIVE: "显著透支",
    ValuationView.INSUFFICIENT: "无法可靠估值",
}
_PRICING_LABELS: Dict[PricingStatus, str] = {
    PricingStatus.UNDER_REFLECTED: "尚未充分反映",
    PricingStatus.PARTLY_REFLECTED: "部分反映",
    PricingStatus.LARGELY_REFLECTED: "大致充分反映",
    PricingStatus.OVER_REFLECTED: "过度反映",
    PricingStatus.UNCERTAIN: "证据不足",
}


def _pct(value: Optional[float]) -> str:
    return "缺失" if value is None else f"{value:.1%}"


def _multiple(value: Optional[float]) -> str:
    return "缺失" if value is None else f"{value:.1f}x"


def _price(value: Optional[float], currency: str) -> str:
    return "暂无法可靠计算" if value is None else f"{currency} {value:,.2f}"


def render_markdown(state: ResearchState) -> str:
    if state.blueprint is None or state.synthesis is None or state.valuation is None:
        raise ValueError("research state is incomplete")
    s = state.snapshot
    synthesis = state.synthesis
    valuation = state.valuation
    currency = "HKD" if state.security.exchange == Exchange.HONG_KONG else "CNY"
    lines = [
        f"# {s.name}（{state.security.symbol}）公司研究报告",
        "",
        f"- 研究日：{state.as_of.isoformat()}",
        f"- 行情时点：{s.as_of.isoformat()}，收盘价 {_price(s.close, currency)}",
        f"- 研究周期：{state.blueprint.horizon}",
        f"- 综合置信度：{synthesis.confidence:.0%}",
        "",
        "## 核心结论与主要矛盾",
        "",
        f"- 企业质量：**{_QUALITY_LABELS[synthesis.company_quality]}**",
        f"- 增长势头：**{_GROWTH_LABELS[synthesis.growth_momentum]}**",
        f"- 估值状态：**{_VALUATION_LABELS[valuation.view]}**",
        f"- 市场计价：**{_PRICING_LABELS[valuation.pricing_status]}**",
        f"- 一句话 thesis：{synthesis.thesis}",
        f"- 主要矛盾：{synthesis.central_tension}",
        "",
        "### 决定性证据",
        "",
    ]
    lines.extend(f"- {item}" for item in synthesis.decisive_evidence or ["证据不足"])
    lines.extend(["", "### 最强反证", ""])
    lines.extend(
        f"- {item}" for item in synthesis.strongest_counterarguments or ["尚未形成有效反证"]
    )

    lines.extend(
        [
            "",
            "## 商业模式与价值驱动",
            "",
            synthesis.business_model,
            "",
            f"盈利与现金流引擎：{synthesis.earnings_engine}",
            "",
            "本公司优先核验的 KPI：",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in state.blueprint.key_metrics)

    lines.extend(
        [
            "",
            "## 盈利能力、质量与财务变化",
            "",
            "| 当前结构化快照 | 数值 |",
            "|---|---:|",
            f"| ROE | {_pct(s.roe)} |",
            f"| 营收增长 | {_pct(s.revenue_growth)} |",
            f"| 利润增长 | {_pct(s.profit_growth)} |",
            f"| 资产负债率 | {_pct(s.debt_ratio)} |",
            f"| PE TTM | {_multiple(s.pe_ttm)} |",
            f"| PB | {_multiple(s.pb)} |",
            "",
            "结构化快照不包含多期利润率、ROIC、分部现金流和资本配置，正式判断必须回查财报。",
            "",
            "## 增长点与增长势头",
            "",
            synthesis.growth_momentum_summary,
            "",
        ]
    )
    lines.extend(f"- {item}" for item in synthesis.growth_drivers)

    lines.extend(
        [
            "",
            "## 竞争与可比基准",
            "",
            f"当前状态：{state.blueprint.peer_comparison_status}。{synthesis.peer_context}",
            "",
            "## 股价反映了多少",
            "",
            valuation.priced_in_summary,
            "",
            f"判断：**{_PRICING_LABELS[valuation.pricing_status]}**。该判断必须说明被计价的是哪些经营假设，而不是只比较涨跌幅。",
            "",
            "## 估值、安全边际与价格区间",
            "",
            f"- 适用方法：{'；'.join(valuation.methods)}",
            f"- 当前价格：{_price(valuation.current_price, currency)}",
            f"- 安全边际：{_pct(valuation.safety_margin_pct)}",
        ]
    )
    lines.extend(f"- 安全边际依据：{item}" for item in valuation.safety_margin_drivers)
    if valuation.fair_value_base is not None:
        lines.extend(
            [
                "",
                "| 情景或价格区域 | 价格 |",
                "|---|---:|",
                f"| Bear 情景价值 | {_price(valuation.fair_value_low, currency)} |",
                f"| Base 情景价值 | {_price(valuation.fair_value_base, currency)} |",
                f"| Bull 情景价值 | {_price(valuation.fair_value_high, currency)} |",
                f"| 理想买入上限 | {_price(valuation.ideal_buy_below, currency)} |",
                f"| 可接受买入上限 | {_price(valuation.acceptable_buy_below, currency)} |",
                (
                    f"| 合理持有区间 | {_price(valuation.reasonable_hold_low, currency)}"
                    f" – {_price(valuation.reasonable_hold_high, currency)} |"
                ),
                f"| 估值偏贵/卖出复核 | ≥ {_price(valuation.sell_review_above, currency)} |",
            ]
        )
        if valuation.assumptions:
            lines.extend(["", "情景假设：", ""])
            lines.extend(f"- {item}" for item in valuation.assumptions)
    else:
        lines.extend(
            [
                "",
                "当前证据不足以形成可信价格区间，缺失输入：",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in valuation.missing_inputs)

    lines.extend(["", "## 风险、证伪与复核", "", "### 主要风险", ""])
    lines.extend(f"- {item}" for item in synthesis.risks or ["尚未完成风险取证"])
    lines.extend(["", "### Thesis invalidation", ""])
    lines.extend(f"- {item}" for item in synthesis.invalidation_conditions)
    lines.extend(["", "### 关键监测指标", ""])
    lines.extend(f"- {item}" for item in synthesis.monitoring_indicators)
    lines.extend(["", f"综合判断：{synthesis.conclusion}"])

    lines.extend(["", "## 证据边界与来源", ""])
    stale = [item for item in state.evidence if not item.point_in_time]
    if s.days_since_market_data > 0:
        lines.append(f"- 行情滞后：{s.days_since_market_data} 天")
    if stale:
        lines.append(f"- 非 point-in-time 证据：{', '.join(item.evidence_id for item in stale)}")
    for item in state.evidence:
        suffix = f"（[原文]({item.url})）" if item.url else ""
        lines.append(
            f"- `{item.evidence_id}` {item.source} / {item.title} / "
            f"发布 {item.published_at.isoformat()}{suffix}"
        )
    lines.extend(
        [
            "",
            "---",
            "本报告仅用于公司研究与估值判断，不构成投资建议。",
        ]
    )
    return "\n".join(lines) + "\n"


def write_reports(state: ResearchState, output_dir: Path) -> tuple:
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{state.as_of.isoformat()}-{state.security.symbol}-{state.run_id[:8]}"
    markdown_path = output_dir / f"{stem}.md"
    json_path = output_dir / f"{stem}.json"
    markdown_path.write_text(render_markdown(state), encoding="utf-8")
    json_path.write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return markdown_path, json_path
