"""A dependency-free bridge from validated JSON snapshots to the research workflow."""

from datetime import date
import json
from pathlib import Path
from typing import Any, Dict, List

from ..domain import Evidence, MarketSnapshot, ValuationContext
from ..market import SecurityId


class JsonFileDataProvider:
    """Read a point-in-time dataset keyed by normalized security symbol.

    The adapter is deliberately strict: future snapshots and absent securities fail
    loudly instead of silently falling back to demo or current data.
    """

    name = "json-file"

    def __init__(self, path: Path) -> None:
        self.path = path
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not isinstance(payload.get("securities"), dict):
            raise ValueError("JSON data file must contain a 'securities' object")
        self._securities: Dict[str, Dict[str, Any]] = payload["securities"]

    def _record(self, security: SecurityId) -> Dict[str, Any]:
        try:
            record = self._securities[security.symbol]
        except KeyError as exc:
            raise KeyError(f"{security.symbol} is absent from {self.path}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"record for {security.symbol} must be an object")
        return record

    def get_snapshot(self, security: SecurityId, as_of: date) -> MarketSnapshot:
        record = self._record(security)
        snapshot_date = date.fromisoformat(str(record["as_of"]))
        if snapshot_date > as_of:
            raise ValueError(
                f"snapshot for {security.symbol} is from {snapshot_date}, after research date {as_of}"
            )
        values = dict(record["snapshot"])
        values["days_since_market_data"] = max(
            int(values.get("days_since_market_data", 0)), (as_of - snapshot_date).days
        )
        return MarketSnapshot(security=security, as_of=snapshot_date, **values)

    def get_evidence(self, security: SecurityId, as_of: date) -> List[Evidence]:
        items = self._record(security).get("evidence", [])
        if not isinstance(items, list):
            raise ValueError(f"evidence for {security.symbol} must be a list")
        evidence = []
        for item in items:
            values = dict(item)
            values["published_at"] = date.fromisoformat(str(values["published_at"]))
            values["observed_at"] = date.fromisoformat(str(values.get("observed_at", as_of)))
            if values.get("period_end") is not None:
                values["period_end"] = date.fromisoformat(str(values["period_end"]))
            evidence.append(Evidence(**values))
        return evidence

    def get_valuation_context(
        self, security: SecurityId, as_of: date
    ) -> ValuationContext:
        values = self._record(security).get("valuation_context")
        if values is None:
            return ValuationContext()
        if not isinstance(values, dict):
            raise ValueError(f"valuation_context for {security.symbol} must be an object")
        return ValuationContext(**values)
