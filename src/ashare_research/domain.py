"""Typed, serializable objects for company research and valuation."""

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .market import SecurityId


class CompanyQuality(str, Enum):
    EXCELLENT = "excellent"
    GOOD = "good"
    MIXED = "mixed"
    WEAK = "weak"
    INSUFFICIENT = "insufficient_data"


class GrowthMomentum(str, Enum):
    ACCELERATING = "accelerating"
    STEADY = "steady"
    SLOWING = "slowing"
    REVERSING = "reversing"
    UNCERTAIN = "uncertain"


class ValuationView(str, Enum):
    ATTRACTIVE = "attractive"
    REASONABLE = "reasonable"
    DEMANDING = "demanding"
    EXCESSIVE = "excessive"
    INSUFFICIENT = "insufficient_data"


class PricingStatus(str, Enum):
    UNDER_REFLECTED = "under_reflected"
    PARTLY_REFLECTED = "partly_reflected"
    LARGELY_REFLECTED = "largely_reflected"
    OVER_REFLECTED = "over_reflected"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source: str
    title: str
    observed_at: date
    published_at: date
    content: str
    url: Optional[str] = None
    category: str = "other"
    source_tier: str = "aggregator"
    point_in_time: bool = True
    period_end: Optional[date] = None
    currency: Optional[str] = None
    unit: Optional[str] = None
    accounting_basis: Optional[str] = None

    def __post_init__(self) -> None:
        if self.published_at > self.observed_at:
            raise ValueError("evidence published_at cannot be later than observed_at")


@dataclass(frozen=True)
class MarketSnapshot:
    security: SecurityId
    as_of: date
    name: str
    industry: str
    close: float
    return_20d: float
    return_60d: float
    ma20_gap: float
    volume_ratio: float
    pe_ttm: Optional[float]
    pb: Optional[float]
    roe: Optional[float]
    revenue_growth: Optional[float]
    profit_growth: Optional[float]
    debt_ratio: Optional[float]
    capital_flow_score: float
    news_sentiment: float
    is_st: bool = False
    suspended: bool = False
    days_since_market_data: int = 0

    def __post_init__(self) -> None:
        if self.close <= 0:
            raise ValueError("close must be positive")
        if self.volume_ratio < 0:
            raise ValueError("volume_ratio cannot be negative")
        if self.days_since_market_data < 0:
            raise ValueError("days_since_market_data cannot be negative")


@dataclass(frozen=True)
class ValuationContext:
    """Auditable scenario values supplied by a provider or external valuation model.

    The deterministic baseline never manufactures these values from a generic PE rule.
    Either all three scenario values are supplied or none are.
    """

    methods: List[str] = field(default_factory=list)
    fair_value_low: Optional[float] = None
    fair_value_base: Optional[float] = None
    fair_value_high: Optional[float] = None
    assumptions: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        values = (self.fair_value_low, self.fair_value_base, self.fair_value_high)
        supplied = [value is not None for value in values]
        if any(supplied) and not all(supplied):
            raise ValueError("fair-value scenarios must provide low, base, and high together")
        if all(supplied):
            low, base, high = values
            assert low is not None and base is not None and high is not None
            if low <= 0 or not low <= base <= high:
                raise ValueError("fair-value scenarios must be positive and ordered")


@dataclass(frozen=True)
class ResearchBlueprint:
    company_archetype: str
    horizon: str
    central_question: str
    key_metrics: List[str]
    selected_roles: List[str]
    role_rationales: Dict[str, str]
    peer_comparison_status: str
    peer_policy: str


@dataclass(frozen=True)
class AnalystReport:
    role: str
    conclusion: str
    confidence: float
    key_findings: List[str]
    counterarguments: List[str]
    unknowns: List[str]
    evidence_ids: List[str]

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("analyst confidence must be between 0 and 1")


@dataclass(frozen=True)
class ValuationAssessment:
    methods: List[str]
    current_price: float
    view: ValuationView
    pricing_status: PricingStatus
    priced_in_summary: str
    fair_value_low: Optional[float]
    fair_value_base: Optional[float]
    fair_value_high: Optional[float]
    safety_margin_pct: Optional[float]
    safety_margin_drivers: List[str]
    ideal_buy_below: Optional[float]
    acceptable_buy_below: Optional[float]
    reasonable_hold_low: Optional[float]
    reasonable_hold_high: Optional[float]
    sell_review_above: Optional[float]
    assumptions: List[str]
    missing_inputs: List[str]
    confidence: float

    def __post_init__(self) -> None:
        if self.current_price <= 0:
            raise ValueError("current_price must be positive")
        if self.safety_margin_pct is not None and not 0 <= self.safety_margin_pct < 1:
            raise ValueError("safety_margin_pct must be in [0, 1)")
        if not 0 <= self.confidence <= 1:
            raise ValueError("valuation confidence must be between 0 and 1")


@dataclass(frozen=True)
class ResearchSynthesis:
    company_quality: CompanyQuality
    growth_momentum: GrowthMomentum
    confidence: float
    thesis: str
    central_tension: str
    business_model: str
    earnings_engine: str
    growth_drivers: List[str]
    growth_momentum_summary: str
    peer_context: str
    decisive_evidence: List[str]
    strongest_counterarguments: List[str]
    risks: List[str]
    invalidation_conditions: List[str]
    monitoring_indicators: List[str]
    conclusion: str

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("synthesis confidence must be between 0 and 1")


@dataclass
class ResearchState:
    run_id: str
    security: SecurityId
    as_of: date
    snapshot: MarketSnapshot
    evidence: List[Evidence]
    valuation_context: ValuationContext = field(default_factory=ValuationContext)
    blueprint: Optional[ResearchBlueprint] = None
    analyst_reports: List[AnalystReport] = field(default_factory=list)
    valuation: Optional[ValuationAssessment] = None
    synthesis: Optional[ResearchSynthesis] = None
    trace: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        def normalize(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, (date, datetime)):
                return value.isoformat()
            if isinstance(value, dict):
                return {key: normalize(item) for key, item in value.items()}
            if isinstance(value, list):
                return [normalize(item) for item in value]
            return value

        return normalize(asdict(self))
