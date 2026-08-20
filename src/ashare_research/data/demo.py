"""Deterministic offline fixtures for smoke tests and UI development."""

from datetime import date
from typing import Dict, List

from ..domain import Evidence, MarketSnapshot, ValuationContext
from ..market import SecurityId


_FIXTURES: Dict[str, Dict[str, object]] = {
    "600519.SH": {
        "name": "贵州茅台",
        "industry": "白酒",
        "close": 1488.0,
        "return_20d": 0.052,
        "return_60d": 0.084,
        "ma20_gap": 0.031,
        "volume_ratio": 1.12,
        "pe_ttm": 24.5,
        "pb": 8.2,
        "roe": 0.31,
        "revenue_growth": 0.12,
        "profit_growth": 0.14,
        "debt_ratio": 0.18,
        "capital_flow_score": 0.25,
        "news_sentiment": 0.20,
    },
    "300750.SZ": {
        "name": "宁德时代",
        "industry": "电池",
        "close": 265.0,
        "return_20d": -0.028,
        "return_60d": 0.036,
        "ma20_gap": -0.012,
        "volume_ratio": 0.94,
        "pe_ttm": 21.0,
        "pb": 4.1,
        "roe": 0.21,
        "revenue_growth": 0.08,
        "profit_growth": 0.19,
        "debt_ratio": 0.56,
        "capital_flow_score": -0.08,
        "news_sentiment": 0.05,
    },
    "00700.HK": {
        "name": "腾讯控股",
        "industry": "互联网服务",
        "close": 578.0,
        "return_20d": 0.038,
        "return_60d": 0.071,
        "ma20_gap": 0.024,
        "volume_ratio": 1.08,
        "pe_ttm": 21.8,
        "pb": 4.2,
        "roe": 0.23,
        "revenue_growth": 0.11,
        "profit_growth": 0.17,
        "debt_ratio": 0.38,
        "capital_flow_score": 0.16,
        "news_sentiment": 0.12,
    },
}

_VALUATION_FIXTURES: Dict[str, Dict[str, object]] = {
    "600519.SH": {
        "methods": ["正常化 PE", "DCF", "自身历史区间"],
        "fair_value_low": 1300.0,
        "fair_value_base": 1650.0,
        "fair_value_high": 1950.0,
        "assumptions": ["仅为离线工作流演示的合成情景，不代表真实估值"],
    },
    "300750.SZ": {
        "methods": ["周期正常化盈利", "EV/EBITDA", "DCF"],
        "fair_value_low": 190.0,
        "fair_value_base": 280.0,
        "fair_value_high": 360.0,
        "assumptions": ["仅为离线工作流演示的合成情景，不代表真实估值"],
    },
    "00700.HK": {
        "methods": ["SOTP", "DCF", "单位经济反向估值"],
        "fair_value_low": 450.0,
        "fair_value_base": 620.0,
        "fair_value_high": 760.0,
        "assumptions": ["仅为离线工作流演示的合成情景，不代表真实估值"],
    },
}


class DemoDataProvider:
    name = "demo"

    def get_snapshot(self, security: SecurityId, as_of: date) -> MarketSnapshot:
        values = _FIXTURES.get(security.symbol)
        if values is None:
            values = {
                "name": f"示例证券{security.code}",
                "industry": "未知",
                "close": 10.0,
                "return_20d": 0.0,
                "return_60d": 0.0,
                "ma20_gap": 0.0,
                "volume_ratio": 1.0,
                "pe_ttm": None,
                "pb": None,
                "roe": None,
                "revenue_growth": None,
                "profit_growth": None,
                "debt_ratio": None,
                "capital_flow_score": 0.0,
                "news_sentiment": 0.0,
            }
        return MarketSnapshot(security=security, as_of=as_of, **values)  # type: ignore[arg-type]

    def get_evidence(self, security: SecurityId, as_of: date) -> List[Evidence]:
        return [
            Evidence(
                evidence_id="demo-market",
                source="offline-demo",
                title="离线行情与因子快照",
                observed_at=as_of,
                published_at=as_of,
                content="用于验证工作流的合成数据，不代表真实行情。",
                category="market",
            ),
            Evidence(
                evidence_id="demo-financial",
                source="offline-demo",
                title="离线财务快照",
                observed_at=as_of,
                published_at=as_of,
                content="用于验证 schema 与一体化报告的合成数据。",
                category="fundamental",
            ),
            Evidence(
                evidence_id="demo-valuation",
                source="offline-demo",
                title="离线估值情景",
                observed_at=as_of,
                published_at=as_of,
                content="仅用于验证动态安全边际和价格区间，不代表真实估值。",
                category="valuation",
            ),
        ]

    def get_valuation_context(
        self, security: SecurityId, as_of: date
    ) -> ValuationContext:
        values = _VALUATION_FIXTURES.get(security.symbol)
        if values is None:
            return ValuationContext()
        return ValuationContext(evidence_ids=["demo-valuation"], **values)  # type: ignore[arg-type]
