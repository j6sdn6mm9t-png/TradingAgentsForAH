"""Evidence-led synthesis and company-specific valuation bands."""

from statistics import mean
from typing import List, Optional

from ..domain import (
    CompanyQuality,
    GrowthMomentum,
    PricingStatus,
    ResearchState,
    ResearchSynthesis,
    ValuationAssessment,
    ValuationView,
)


def _dedupe(items: List[str]) -> List[str]:
    return list(dict.fromkeys(item for item in items if item))


_QUALITY_TEXT = {
    CompanyQuality.EXCELLENT: "优秀",
    CompanyQuality.GOOD: "良好",
    CompanyQuality.MIXED: "一般",
    CompanyQuality.WEAK: "较弱",
    CompanyQuality.INSUFFICIENT: "证据不足",
}
_VALUATION_TEXT = {
    ValuationView.ATTRACTIVE: "有吸引力",
    ValuationView.REASONABLE: "合理",
    ValuationView.DEMANDING: "偏贵",
    ValuationView.EXCESSIVE: "显著透支",
    ValuationView.INSUFFICIENT: "无法可靠估值",
}
_PRICING_TEXT = {
    PricingStatus.UNDER_REFLECTED: "尚未充分反映",
    PricingStatus.PARTLY_REFLECTED: "部分反映",
    PricingStatus.LARGELY_REFLECTED: "大致充分反映",
    PricingStatus.OVER_REFLECTED: "过度反映",
    PricingStatus.UNCERTAIN: "证据不足",
}


def _quality(state: ResearchState) -> CompanyQuality:
    s = state.snapshot
    values = (s.roe, s.revenue_growth, s.profit_growth, s.debt_ratio)
    known = sum(value is not None for value in values)
    if known < 2:
        return CompanyQuality.INSUFFICIENT
    roe = s.roe or 0.0
    revenue = s.revenue_growth or 0.0
    profit = s.profit_growth or 0.0
    debt = s.debt_ratio if s.debt_ratio is not None else 0.5
    if roe >= 0.25 and revenue > 0 and profit > 0 and debt <= 0.50:
        return CompanyQuality.EXCELLENT
    if roe >= 0.12 and revenue >= 0 and profit >= 0 and debt <= 0.65:
        return CompanyQuality.GOOD
    if revenue < 0 and profit < 0 and (roe <= 0 or debt > 0.70):
        return CompanyQuality.WEAK
    return CompanyQuality.MIXED


def _growth_momentum(state: ResearchState) -> GrowthMomentum:
    s = state.snapshot
    if s.revenue_growth is None or s.profit_growth is None:
        return GrowthMomentum.UNCERTAIN
    if s.revenue_growth < 0 and s.profit_growth < 0:
        return GrowthMomentum.REVERSING
    # A single point can establish current growth, but not its slope.
    return GrowthMomentum.UNCERTAIN


def _valuation_methods(state: ResearchState) -> List[str]:
    if state.valuation_context.methods:
        return state.valuation_context.methods
    assert state.blueprint is not None
    archetype = state.blueprint.company_archetype
    if "品牌消费" in archetype:
        return ["正常化 PE", "DCF", "自身历史区间"]
    if "平台" in archetype:
        return ["SOTP", "DCF", "单位经济反向估值"]
    if "资本密集" in archetype:
        return ["周期正常化盈利", "EV/EBITDA", "DCF/重置价值"]
    if "资产负债表" in archetype:
        return ["PB-ROE", "剩余收益模型", "股息折现"]
    if "研发管线" in archetype:
        return ["风险调整 NPV", "里程碑情景", "现金价值"]
    return ["公司特定 DCF", "分部估值", "自身历史与有效可比基准"]


class ValuationEngine:
    def assess(self, state: ResearchState) -> ValuationAssessment:
        assert state.blueprint is not None
        context = state.valuation_context
        methods = _valuation_methods(state)
        quality = _quality(state)
        quality_margins = {
            CompanyQuality.EXCELLENT: (0.12, "较高资本回报、正增长与较低杠杆支持较低质量折价"),
            CompanyQuality.GOOD: (0.16, "财务质量良好但仍需为经营预测误差保留折价"),
            CompanyQuality.MIXED: (0.22, "企业质量存在分歧，需要更高的预测误差折价"),
            CompanyQuality.WEAK: (0.28, "财务质量偏弱，需要覆盖永久性损失风险"),
            CompanyQuality.INSUFFICIENT: (0.25, "财务证据不足，安全边际需补偿未知量"),
        }
        margin, quality_driver = quality_margins[quality]
        drivers = [quality_driver]

        archetype = state.blueprint.company_archetype
        if "周期" in archetype or "研发管线" in archetype:
            margin += 0.05
            drivers.append("周期或里程碑结果波动较大，需要额外安全边际")
        if state.snapshot.debt_ratio is not None and state.snapshot.debt_ratio > 0.60:
            margin += 0.04
            drivers.append("杠杆偏高，加入现金流与再融资风险折价")
        if state.snapshot.days_since_market_data > 0:
            margin += 0.02
            drivers.append("行情数据滞后，价格判断置信度下降")
        margin = min(0.40, max(0.10, margin))

        low = context.fair_value_low
        base = context.fair_value_base
        high = context.fair_value_high
        if low is None or base is None or high is None:
            return ValuationAssessment(
                methods=methods,
                current_price=state.snapshot.close,
                view=ValuationView.INSUFFICIENT,
                pricing_status=PricingStatus.UNCERTAIN,
                priced_in_summary=(
                    "当前仅有交易倍数和价格趋势，缺少可审计的正常化盈利、情景价值、"
                    "一致预期修正与事件反应，不能可靠判断增长已被计价多少。"
                ),
                fair_value_low=None,
                fair_value_base=None,
                fair_value_high=None,
                safety_margin_pct=None,
                safety_margin_drivers=drivers,
                ideal_buy_below=None,
                acceptable_buy_below=None,
                reasonable_hold_low=None,
                reasonable_hold_high=None,
                sell_review_above=None,
                assumptions=context.assumptions,
                missing_inputs=[
                    "bull/base/bear 正常化盈利或现金流",
                    "各情景适用估值参数及证据",
                    "反向估值隐含经营假设",
                    "一致预期修正与关键事件价格反应",
                ],
                confidence=0.20,
            )

        ideal = base * (1 - margin)
        acceptable = base * (1 - margin / 2)
        current = state.snapshot.close
        if current <= ideal:
            view = ValuationView.ATTRACTIVE
            pricing = PricingStatus.UNDER_REFLECTED
        elif current <= acceptable:
            view = ValuationView.REASONABLE
            pricing = PricingStatus.PARTLY_REFLECTED
        elif current <= high:
            view = ValuationView.DEMANDING
            pricing = PricingStatus.LARGELY_REFLECTED
        else:
            view = ValuationView.EXCESSIVE
            pricing = PricingStatus.OVER_REFLECTED
        gap = current / base - 1
        return ValuationAssessment(
            methods=methods,
            current_price=current,
            view=view,
            pricing_status=pricing,
            priced_in_summary=(
                f"当前价相对 base 情景价值偏离 {gap:+.1%}。该状态仅由已提供的情景价值推断，"
                "正式报告仍需以反向估值、一致预期修正和事件反应交叉验证。"
            ),
            fair_value_low=low,
            fair_value_base=base,
            fair_value_high=high,
            safety_margin_pct=margin,
            safety_margin_drivers=drivers,
            ideal_buy_below=ideal,
            acceptable_buy_below=acceptable,
            reasonable_hold_low=acceptable,
            reasonable_hold_high=high,
            sell_review_above=high,
            assumptions=context.assumptions,
            missing_inputs=[],
            confidence=0.60 if context.evidence_ids and context.assumptions else 0.40,
        )


class ResearchLead:
    def synthesize(self, state: ResearchState) -> ResearchSynthesis:
        if state.blueprint is None or state.valuation is None:
            raise ValueError("research blueprint and valuation are required")
        s = state.snapshot
        quality = _quality(state)
        momentum = _growth_momentum(state)
        confidences = [report.confidence for report in state.analyst_reports]
        confidence = min(0.85, mean(confidences)) if confidences else 0.0
        if state.valuation.view == ValuationView.INSUFFICIENT:
            confidence = min(confidence, 0.50)

        findings = _dedupe(
            [item for report in state.analyst_reports for item in report.key_findings]
        )
        counterarguments = _dedupe(
            [item for report in state.analyst_reports for item in report.counterarguments]
        )
        risks = counterarguments[:5]
        if s.is_st:
            risks.insert(0, "风险警示状态可能对应持续经营、财务或治理问题")
        if s.suspended:
            risks.insert(0, "停牌导致信息与价格发现不完整")

        growth_summary = (
            f"最近快照显示营收增长 {_fmt_growth(s.revenue_growth)}、利润增长 "
            f"{_fmt_growth(s.profit_growth)}；但缺少多期贡献拆分，不能判断增长斜率。"
        )
        engine = (
            f"当前可见财务结果为 ROE {_fmt_growth(s.roe)}、资产负债率 "
            f"{_fmt_growth(s.debt_ratio)}。真正的盈利引擎仍需按分部把量、价、成本、"
            "资本投入与现金回收连接起来。"
        )
        drivers = [
            f"围绕 {metric} 验证其对收入、利润和现金流的边际贡献"
            for metric in state.blueprint.key_metrics[:4]
        ]
        invalidation = [
            "核心业务 KPI 连续恶化且无法由可逆周期或基数解释",
            "正常化利润或自由现金流显著低于 base 情景",
            "资本回报持续低于资本成本，或治理与会计证据破坏原 thesis",
        ]
        valuation_clause = (
            "已有可审计情景价值，可据动态安全边际形成价格区间"
            if state.valuation.fair_value_base is not None
            else "尚缺可靠估值锚，当前不能给出可信价格区间"
        )
        thesis = (
            f"{s.name}初步属于{state.blueprint.company_archetype}；公司质量判断为"
            f"{_QUALITY_TEXT[quality]}，{valuation_clause}。"
        )
        return ResearchSynthesis(
            company_quality=quality,
            growth_momentum=momentum,
            confidence=confidence,
            thesis=thesis,
            central_tension=state.blueprint.central_question,
            business_model=(
                f"初步商业类型为“{state.blueprint.company_archetype}”。当前结构化快照不含"
                "客户、收费方式和分部经济性，正式结论必须回到年报与业务披露。"
            ),
            earnings_engine=engine,
            growth_drivers=drivers,
            growth_momentum_summary=growth_summary,
            peer_context=state.blueprint.peer_policy,
            decisive_evidence=findings[:5],
            strongest_counterarguments=counterarguments[:3],
            risks=_dedupe(risks),
            invalidation_conditions=invalidation,
            monitoring_indicators=state.blueprint.key_metrics,
            conclusion=(
                f"研究应围绕“{state.blueprint.central_question}”继续取证；"
                f"当前估值判断为{_VALUATION_TEXT[state.valuation.view]}，市场计价判断为"
                f"{_PRICING_TEXT[state.valuation.pricing_status]}。"
            ),
        )


def _fmt_growth(value: Optional[float]) -> str:
    return "缺失" if value is None else f"{value:.1%}"
