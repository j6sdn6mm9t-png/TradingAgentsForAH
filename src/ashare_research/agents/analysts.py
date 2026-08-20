"""Company-adaptive research planning and deterministic baseline analysts."""

from typing import Dict, List, Optional, Tuple

from .base import Analyst
from ..domain import AnalystReport, MarketSnapshot, ResearchBlueprint, ResearchState


def _known(*values: Optional[float]) -> float:
    return sum(value is not None for value in values) / len(values)


def _evidence_ids(state: ResearchState, *categories: str) -> List[str]:
    wanted = set(categories)
    return [
        item.evidence_id
        for item in state.evidence
        if not wanted or item.category in wanted
    ]


def _fmt_pct(value: Optional[float]) -> str:
    return "缺失" if value is None else f"{value:.1%}"


_PROFILE_RULES: List[Tuple[Tuple[str, ...], Dict[str, object]]] = [
    (
        ("白酒", "食品", "饮料", "消费", "零售", "家电"),
        {
            "archetype": "品牌消费与渠道经营",
            "horizon": "覆盖至少两个完整经营年度及一轮渠道库存变化",
            "question": "品牌与渠道优势能否继续转化为量价增长、利润率和现金回收，而当前估值是否已经透支这种确定性？",
            "metrics": ["销量与 ASP", "渠道动销与库存", "产品结构", "毛利率", "经营现金流/净利润"],
            "specialist": "brand_channel",
            "peer": "仅选择品牌力、价格带、渠道结构和增长阶段接近的公司；若稀缺性显著，优先自身历史与现金流基准。",
        },
    ),
    (
        ("互联网", "软件", "平台", "游戏", "传媒"),
        {
            "archetype": "平台与数字化单位经济",
            "horizon": "覆盖产品变现、用户行为和投入回收能够被连续财报验证的周期",
            "question": "用户与生态优势能否转化为可持续的单位经济和自由现金流，新增变现是否已被市场计价？",
            "metrics": ["MAU/DAU 与时长", "ARPU/take rate", "获客与留存", "分部利润率", "自由现金流"],
            "specialist": "unit_economics",
            "peer": "按用户场景、变现模式和资本投入选择可比对象；多业务平台优先 SOTP，不强行使用单一同业倍数。",
        },
    ),
    (
        ("电池", "新能源", "汽车", "机械", "设备", "半导体", "化工", "钢铁", "有色"),
        {
            "archetype": "资本密集制造与周期供需",
            "horizon": "覆盖产能投放、库存、价格和资本开支形成的一轮供需周期",
            "question": "销量与份额增长能否抵消价格和利用率压力，并在资本开支后形成高于资本成本的回报？",
            "metrics": ["销量/出货量", "ASP 与单位成本", "产能利用率", "订单与库存", "ROIC 与自由现金流"],
            "specialist": "cycle_supply",
            "peer": "比较产品结构、技术路线、客户结构和产能周期相近的公司，并对会计口径与景气位置作正常化调整。",
        },
    ),
    (
        ("银行", "保险", "证券", "金融"),
        {
            "archetype": "资产负债表与监管资本经营",
            "horizon": "覆盖信用成本、资产负债重定价和资本充足率的一轮变化",
            "question": "资产质量、息差或承保质量能否支撑可持续 ROE，当前 PB 隐含了怎样的信用和增长预期？",
            "metrics": ["净息差/承保利润", "不良与拨备", "资产负债久期", "核心资本充足率", "ROE 与内生资本"],
            "specialist": "balance_sheet_quality",
            "peer": "选择资产结构、区域风险、资本约束和业务结构接近的机构，PB 必须与可持续 ROE 和信用成本联动。",
        },
    ),
    (
        ("医药", "生物", "制药"),
        {
            "archetype": "研发管线与商业化里程碑",
            "horizon": "覆盖关键临床、审批、放量与现金消耗里程碑",
            "question": "核心管线或产品的成功概率、商业价值和融资需求是否支持当前市值？",
            "metrics": ["临床/审批里程碑", "患者渗透率", "单产品峰值销售", "研发效率", "现金消耗与融资期限"],
            "specialist": "pipeline_milestones",
            "peer": "仅比较适应症、阶段、成功概率和商业化权利接近的资产；优先风险调整 NPV，避免用成熟药企 PE 硬比。",
        },
    ),
]

_SPECIALIST_FOCUS = {
    "brand_channel": "量价、产品结构、渠道动销与库存",
    "unit_economics": "用户、留存、ARPU/take rate 与投入回收",
    "cycle_supply": "供需、价格、库存、产能利用率和资本开支",
    "balance_sheet_quality": "资产质量、负债成本、信用损失与监管资本",
    "pipeline_milestones": "研发成功率、审批、商业化和现金消耗",
    "business_specific": "分部经济性和公司独有价值驱动",
}


class ResearchPlanner:
    def plan(self, snapshot: MarketSnapshot) -> ResearchBlueprint:
        profile: Dict[str, object] = {
            "archetype": "待由分部与价值链证据识别的公司特定模式",
            "horizon": "覆盖一个完整经营、现金回收与资本投入周期，待商业模式证据确认",
            "question": "公司真正的价值驱动、增长持续性和当前价格隐含预期分别是什么？",
            "metrics": ["分部收入与利润", "毛利率/经营利润率", "ROIC", "现金转换", "资本开支"],
            "specialist": "business_specific",
            "peer": "先验证是否存在真正可比的商业模式；若不可比，使用自身历史、单位经济、分部或情景估值。",
        }
        for keywords, candidate in _PROFILE_RULES:
            if any(keyword in snapshot.industry for keyword in keywords):
                profile = candidate
                break

        roles = ["business_model", "growth_kpi", "valuation_expectations"]
        if _known(snapshot.roe, snapshot.revenue_growth, snapshot.profit_growth, snapshot.debt_ratio) >= 0.5:
            roles.append("fundamental_quality")
        roles.append(str(profile["specialist"]))
        roles.append("independent_challenge")
        rationales = {
            "business_model": "识别客户、收费方式、价值链和利润池，是选择 KPI 与估值方法的前提",
            "growth_kpi": "区分增长来源、当前贡献、边际趋势和领先指标",
            "valuation_expectations": "把经营假设连接到内在价值和市场隐含预期",
            "fundamental_quality": "已有基础财务字段，需要进一步验证利润、现金流和资本回报质量",
            str(profile["specialist"]): f"该商业类型需要专题核验 {_SPECIALIST_FOCUS[str(profile['specialist'])]}",
            "independent_challenge": "独立攻击增长质量、会计治理和估值假设，避免内部确认偏误",
        }
        return ResearchBlueprint(
            company_archetype=str(profile["archetype"]),
            horizon=str(profile["horizon"]),
            central_question=str(profile["question"]),
            key_metrics=list(profile["metrics"]),  # type: ignore[arg-type]
            selected_roles=roles,
            role_rationales={role: rationales[role] for role in roles},
            peer_comparison_status="待核验是否采用同业比较",
            peer_policy=str(profile["peer"]),
        )


class BusinessModelAnalyst(Analyst):
    role = "business_model"

    def analyze(self, state: ResearchState) -> AnalystReport:
        assert state.blueprint is not None
        return AnalystReport(
            role=self.role,
            conclusion=f"初步归类为“{state.blueprint.company_archetype}”，需用分部披露验证收入到现金流的传导。",
            confidence=0.45 if state.snapshot.industry != "未知" else 0.20,
            key_findings=[f"已识别行业标签：{state.snapshot.industry}"],
            counterarguments=["行业标签可能掩盖多元业务、区域和客户结构差异"],
            unknowns=["分部收入与利润", "客户和收费模式", "竞争壁垒如何转化为 ROIC"],
            evidence_ids=_evidence_ids(state, "company", "filing", "other"),
        )


class FundamentalQualityAnalyst(Analyst):
    role = "fundamental_quality"

    def analyze(self, state: ResearchState) -> AnalystReport:
        s = state.snapshot
        known = _known(s.roe, s.revenue_growth, s.profit_growth, s.debt_ratio)
        findings = [
            f"ROE {_fmt_pct(s.roe)}",
            f"营收增长 {_fmt_pct(s.revenue_growth)}，利润增长 {_fmt_pct(s.profit_growth)}",
            f"资产负债率 {_fmt_pct(s.debt_ratio)}",
        ]
        counterarguments = []
        if s.debt_ratio is not None and s.debt_ratio > 0.60:
            counterarguments.append("较高资产负债率可能放大周期和再融资风险")
        if s.revenue_growth is not None and s.profit_growth is not None:
            if s.profit_growth < s.revenue_growth:
                counterarguments.append("利润增长落后于收入，需拆解价格、成本和费用率")
        return AnalystReport(
            role=self.role,
            conclusion="现有快照可用于提出财务质量问题，但不足以替代多期利润、现金流和资本回报分析。",
            confidence=0.70 * known,
            key_findings=findings,
            counterarguments=counterarguments or ["单期 ROE 与增长率可能受基数和会计口径影响"],
            unknowns=["多期利润率", "ROIC", "自由现金流转换", "资本配置与治理"],
            evidence_ids=_evidence_ids(state, "fundamental", "filing"),
        )


class GrowthKPIAnalyst(Analyst):
    role = "growth_kpi"

    def analyze(self, state: ResearchState) -> AnalystReport:
        s = state.snapshot
        assert state.blueprint is not None
        findings = [
            f"最近快照营收增长 {_fmt_pct(s.revenue_growth)}",
            f"最近快照利润增长 {_fmt_pct(s.profit_growth)}",
            f"应优先追踪：{'、'.join(state.blueprint.key_metrics)}",
        ]
        return AnalystReport(
            role=self.role,
            conclusion="单期增长快照不能判断增长正在加速还是减速，必须补充多期贡献拆分和领先 KPI。",
            confidence=0.40 if s.revenue_growth is not None and s.profit_growth is not None else 0.18,
            key_findings=findings,
            counterarguments=["同比增长可能来自低基数、价格变化、并表或补库存，而非结构性需求"],
            unknowns=["增长贡献拆分", "至少多个报告期的边际变化", "管理层指引与一致预期修正"],
            evidence_ids=_evidence_ids(state, "fundamental", "filing"),
        )


class ValuationExpectationsAnalyst(Analyst):
    role = "valuation_expectations"

    def analyze(self, state: ResearchState) -> AnalystReport:
        s = state.snapshot
        valuation = []
        if s.pe_ttm is not None:
            valuation.append(f"PE TTM {s.pe_ttm:.1f}x")
        if s.pb is not None:
            valuation.append(f"PB {s.pb:.1f}x")
        findings = valuation or ["当前缺少可用估值倍数"]
        findings.append(f"20/60 日价格变化分别为 {s.return_20d:.1%}/{s.return_60d:.1%}")
        return AnalystReport(
            role=self.role,
            conclusion="当前倍数与价格趋势不足以判断市场计价程度；需要反向估值、预测修正和事件反应交叉验证。",
            confidence=0.35 if valuation else 0.12,
            key_findings=findings,
            counterarguments=["绝对 PE/PB 不能脱离正常化盈利、资本强度和增长持续期解释"],
            unknowns=["正常化盈利/现金流", "bull/base/bear 经营假设", "一致预期修正", "历史估值与有效可比基准"],
            evidence_ids=_evidence_ids(state, "valuation", "market"),
        )


class SpecialistAnalyst(Analyst):
    def __init__(self, role: str) -> None:
        self.role = role

    def analyze(self, state: ResearchState) -> AnalystReport:
        focus = _SPECIALIST_FOCUS.get(self.role, "公司特定经营指标")
        return AnalystReport(
            role=self.role,
            conclusion=f"本公司需要专题核验 {focus}，通用财务快照无法替代该分析。",
            confidence=0.25,
            key_findings=[f"专题焦点：{focus}"],
            counterarguments=["未取得公司特定运营数据前，增长来源和持续性仍是假设"],
            unknowns=[focus],
            evidence_ids=_evidence_ids(state, "fundamental", "company", "filing"),
        )


class IndependentChallengeAnalyst(Analyst):
    role = "independent_challenge"

    def analyze(self, state: ResearchState) -> AnalystReport:
        s = state.snapshot
        risks = []
        if s.is_st:
            risks.append("证券处于风险警示状态，需重点核验持续经营与披露风险")
        if s.suspended:
            risks.append("证券处于停牌状态，信息与价格发现可能不完整")
        if s.days_since_market_data > 0:
            risks.append(f"行情快照滞后 {s.days_since_market_data} 天")
        if s.debt_ratio is not None and s.debt_ratio > 0.60:
            risks.append(f"资产负债率 {s.debt_ratio:.1%}，需压力测试现金流和再融资")
        return AnalystReport(
            role=self.role,
            conclusion="独立挑战聚焦增长质量、会计与治理、周期反转及估值隐含假设。",
            confidence=0.65,
            key_findings=risks or ["当前快照未暴露 ST、停牌或明显数据时效硬伤"],
            counterarguments=["没有原始财报、公告和多期数据，不能据此认定风险不存在"],
            unknowns=["会计质量", "治理与关联交易", "最敏感经营假设的压力测试"],
            evidence_ids=_evidence_ids(state, "data_quality", "fundamental", "filing"),
        )


def build_adaptive_analysts(blueprint: ResearchBlueprint) -> List[Analyst]:
    factories = {
        "business_model": BusinessModelAnalyst,
        "growth_kpi": GrowthKPIAnalyst,
        "valuation_expectations": ValuationExpectationsAnalyst,
        "fundamental_quality": FundamentalQualityAnalyst,
        "independent_challenge": IndependentChallengeAnalyst,
    }
    analysts: List[Analyst] = []
    for role in blueprint.selected_roles:
        factory = factories.get(role)
        analysts.append(factory() if factory is not None else SpecialistAnalyst(role))
    return analysts
