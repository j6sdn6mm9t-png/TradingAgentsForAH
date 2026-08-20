"""Stable company-research orchestration API, independent of any LLM framework."""

from dataclasses import replace
from datetime import date
import uuid
from typing import Optional, Sequence

from .agents import ResearchLead, ResearchPlanner, ValuationEngine, build_adaptive_analysts
from .agents.base import Analyst
from .config import ResearchConfig
from .data.base import MarketDataProvider
from .domain import ResearchState
from .market import SecurityId


class ResearchWorkflow:
    def __init__(
        self,
        provider: MarketDataProvider,
        config: Optional[ResearchConfig] = None,
        analysts: Optional[Sequence[Analyst]] = None,
    ) -> None:
        self.provider = provider
        self.config = config or ResearchConfig()
        self._custom_analysts = None if analysts is None else list(analysts)
        self.planner = ResearchPlanner()
        self.valuation_engine = ValuationEngine()
        self.research_lead = ResearchLead()

    def run(self, symbol: str, as_of: date) -> ResearchState:
        security = SecurityId.parse(symbol)
        snapshot = self.provider.get_snapshot(security, as_of)
        if snapshot.security != security:
            raise ValueError("provider returned a snapshot for a different security")
        if snapshot.as_of > as_of:
            raise ValueError("future market snapshot rejected")
        snapshot = replace(
            snapshot,
            days_since_market_data=max(
                snapshot.days_since_market_data, (as_of - snapshot.as_of).days
            ),
        )
        evidence = self.provider.get_evidence(security, as_of)
        if not evidence:
            raise ValueError("provider returned no auditable evidence")
        evidence_ids = [item.evidence_id for item in evidence]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("provider returned duplicate evidence IDs")
        for item in evidence:
            if item.published_at > as_of:
                raise ValueError(f"future evidence rejected: {item.evidence_id}")
            if item.observed_at > as_of:
                raise ValueError(f"future observation rejected: {item.evidence_id}")

        valuation_context = self.provider.get_valuation_context(security, as_of)
        unknown_valuation_evidence = set(valuation_context.evidence_ids) - set(evidence_ids)
        if unknown_valuation_evidence:
            raise ValueError(
                "valuation context cited unknown evidence: "
                f"{sorted(unknown_valuation_evidence)}"
            )

        state = ResearchState(
            run_id=uuid.uuid4().hex,
            security=security,
            as_of=as_of,
            snapshot=snapshot,
            evidence=evidence,
            valuation_context=valuation_context,
            trace=[f"data:{self.provider.name}"],
        )
        state.blueprint = self.planner.plan(snapshot)
        state.trace.append("research:blueprint")
        analysts = (
            build_adaptive_analysts(state.blueprint)
            if self._custom_analysts is None
            else self._custom_analysts
        )
        for analyst in analysts:
            report = analyst.analyze(state)
            unknown_evidence = set(report.evidence_ids) - set(evidence_ids)
            if unknown_evidence:
                raise ValueError(
                    f"analyst {report.role} cited unknown evidence: {sorted(unknown_evidence)}"
                )
            state.analyst_reports.append(report)
            state.trace.append(f"research:{analyst.role}")

        state.valuation = self.valuation_engine.assess(state)
        state.trace.append("research:valuation")
        state.synthesis = self.research_lead.synthesize(state)
        state.trace.append("research:synthesis")
        return state

    def propagate(self, symbol: str, trade_date: str):
        """TradingAgents-style compatibility entry point.

        Returns the full state and typed company synthesis.
        """
        state = self.run(symbol, date.fromisoformat(trade_date))
        return state, state.synthesis
