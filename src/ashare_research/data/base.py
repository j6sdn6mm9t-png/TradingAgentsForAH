"""Provider contract; vendor-specific APIs stay behind this boundary."""

from datetime import date
from typing import List, Protocol

from ..domain import Evidence, MarketSnapshot, ValuationContext
from ..market import SecurityId


class MarketDataProvider(Protocol):
    name: str

    def get_snapshot(self, security: SecurityId, as_of: date) -> MarketSnapshot:
        ...

    def get_evidence(self, security: SecurityId, as_of: date) -> List[Evidence]:
        ...

    def get_valuation_context(
        self, security: SecurityId, as_of: date
    ) -> ValuationContext:
        ...
