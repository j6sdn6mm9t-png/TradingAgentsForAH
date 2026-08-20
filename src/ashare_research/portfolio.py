"""Deterministic paper portfolio shared by simulation and backtesting.

All cash and NAV values use a configurable base currency. Quotes carry an
``fx_to_base`` multiplier so A-share CNY and Hong Kong HKD assets can coexist.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import math
from typing import Dict, List, Mapping, Optional

from .market import Exchange, SecurityId


class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    FILLED = "filled"
    PARTIAL = "partial"
    REJECTED = "rejected"


@dataclass(frozen=True)
class CostSchedule:
    commission_rate: float = 0.0
    minimum_commission: float = 0.0
    sell_stamp_rate: float = 0.0
    transfer_rate: float = 0.0

    def calculate(self, side: OrderSide, notional_local: float) -> float:
        if notional_local <= 0:
            return 0.0
        commission = max(self.minimum_commission, notional_local * self.commission_rate)
        stamp = notional_local * self.sell_stamp_rate if side == OrderSide.SELL else 0.0
        return commission + stamp + notional_local * self.transfer_rate


@dataclass(frozen=True)
class PriceQuote:
    security: SecurityId
    trade_date: date
    open: float
    close: float
    suspended: bool = False
    at_limit_up_open: bool = False
    at_limit_down_open: bool = False
    lot_size: int = 100
    currency: str = "CNY"
    fx_to_base: float = 1.0

    def __post_init__(self) -> None:
        if self.open <= 0 or self.close <= 0:
            raise ValueError("quote prices must be positive")
        if self.lot_size <= 0:
            raise ValueError("lot_size must be positive")
        if self.fx_to_base <= 0:
            raise ValueError("fx_to_base must be positive")


@dataclass
class Position:
    security: SecurityId
    quantity: int
    sellable_quantity: int
    average_cost_local: float
    last_price_local: float
    fx_to_base: float
    opened_at: date

    @property
    def market_value_base(self) -> float:
        return self.quantity * self.last_price_local * self.fx_to_base


@dataclass(frozen=True)
class OrderResult:
    trade_date: date
    security: SecurityId
    side: OrderSide
    requested_quantity: int
    filled_quantity: int
    price_local: float
    fees_base: float
    status: OrderStatus
    reason: str = ""

@dataclass(frozen=True)
class PortfolioSnapshot:
    trade_date: date
    cash_base: float
    market_value_base: float
    total_value_base: float
    position_weights: Dict[str, float]


@dataclass
class PaperPortfolio:
    initial_cash: float
    base_currency: str = "CNY"
    cash_base: float = field(init=False)
    positions: Dict[str, Position] = field(default_factory=dict)
    orders: List[OrderResult] = field(default_factory=list)
    current_date: Optional[date] = None

    def __post_init__(self) -> None:
        if self.initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self.cash_base = float(self.initial_cash)

    @property
    def total_value_base(self) -> float:
        return self.cash_base + sum(item.market_value_base for item in self.positions.values())

    def start_day(self, trade_date: date) -> None:
        if self.current_date is not None and trade_date < self.current_date:
            raise ValueError("portfolio dates must be monotonic")
        if self.current_date != trade_date:
            for position in self.positions.values():
                position.sellable_quantity = position.quantity
        self.current_date = trade_date

    def mark_to_market(self, quotes: Mapping[str, PriceQuote]) -> None:
        for symbol, position in self.positions.items():
            quote = quotes.get(symbol)
            if quote is not None:
                position.last_price_local = quote.close
                position.fx_to_base = quote.fx_to_base

    def _reject(
        self, quote: PriceQuote, side: OrderSide, requested: int, reason: str
    ) -> OrderResult:
        result = OrderResult(
            trade_date=quote.trade_date,
            security=quote.security,
            side=side,
            requested_quantity=requested,
            filled_quantity=0,
            price_local=quote.open,
            fees_base=0.0,
            status=OrderStatus.REJECTED,
            reason=reason,
        )
        self.orders.append(result)
        return result

    def execute(
        self,
        quote: PriceQuote,
        side: OrderSide,
        quantity: int,
        costs: CostSchedule,
    ) -> OrderResult:
        if self.current_date != quote.trade_date:
            raise ValueError("call start_day() before executing orders")
        if quantity <= 0:
            return self._reject(quote, side, quantity, "quantity must be positive")
        if quote.suspended:
            return self._reject(quote, side, quantity, "security is suspended")
        if side == OrderSide.BUY and quote.at_limit_up_open:
            return self._reject(quote, side, quantity, "cannot buy at locked limit-up open")
        if side == OrderSide.SELL and quote.at_limit_down_open:
            return self._reject(quote, side, quantity, "cannot sell at locked limit-down open")

        rounded = (quantity // quote.lot_size) * quote.lot_size
        if rounded <= 0:
            return self._reject(quote, side, quantity, "quantity is below one board lot")
        symbol = quote.security.symbol

        if side == OrderSide.BUY:
            local_per_share = quote.open
            max_lots = int(self.cash_base / (local_per_share * quote.fx_to_base)) // quote.lot_size
            filled = min(rounded, max_lots * quote.lot_size)
            while filled > 0:
                notional_local = filled * local_per_share
                fees_base = costs.calculate(side, notional_local) * quote.fx_to_base
                if notional_local * quote.fx_to_base + fees_base <= self.cash_base + 1e-9:
                    break
                filled -= quote.lot_size
            if filled <= 0:
                return self._reject(quote, side, quantity, "insufficient cash")
            notional_local = filled * local_per_share
            fees_base = costs.calculate(side, notional_local) * quote.fx_to_base
            self.cash_base -= notional_local * quote.fx_to_base + fees_base
            existing = self.positions.get(symbol)
            if existing is None:
                existing = Position(
                    security=quote.security,
                    quantity=0,
                    sellable_quantity=0,
                    average_cost_local=0.0,
                    last_price_local=quote.open,
                    fx_to_base=quote.fx_to_base,
                    opened_at=quote.trade_date,
                )
                self.positions[symbol] = existing
            total_local_cost = (
                existing.average_cost_local * existing.quantity + notional_local
            )
            existing.quantity += filled
            existing.average_cost_local = total_local_cost / existing.quantity
            existing.last_price_local = quote.open
            existing.fx_to_base = quote.fx_to_base
            if quote.security.exchange == Exchange.HONG_KONG:
                existing.sellable_quantity += filled
        else:
            existing = self.positions.get(symbol)
            if existing is None:
                return self._reject(quote, side, quantity, "no position")
            available = (
                existing.quantity
                if quote.security.exchange == Exchange.HONG_KONG
                else existing.sellable_quantity
            )
            filled = min(rounded, available)
            if filled <= 0:
                return self._reject(quote, side, quantity, "T+1 or no sellable quantity")
            notional_local = filled * quote.open
            fees_base = costs.calculate(side, notional_local) * quote.fx_to_base
            self.cash_base += notional_local * quote.fx_to_base - fees_base
            existing.quantity -= filled
            existing.sellable_quantity = max(0, existing.sellable_quantity - filled)
            existing.last_price_local = quote.open
            existing.fx_to_base = quote.fx_to_base
            if existing.quantity == 0:
                del self.positions[symbol]

        result = OrderResult(
            trade_date=quote.trade_date,
            security=quote.security,
            side=side,
            requested_quantity=quantity,
            filled_quantity=filled,
            price_local=quote.open,
            fees_base=fees_base,
            status=OrderStatus.FILLED if filled == rounded else OrderStatus.PARTIAL,
            reason="" if filled == rounded else "filled quantity constrained by cash or inventory",
        )
        self.orders.append(result)
        return result

    def rebalance(
        self,
        target_weights: Mapping[str, float],
        quotes: Mapping[str, PriceQuote],
        cost_schedules: Mapping[Exchange, CostSchedule],
        maximum_single_weight: float = 0.10,
    ) -> List[OrderResult]:
        if self.current_date is None:
            raise ValueError("call start_day() before rebalancing")
        if not 0 < maximum_single_weight <= 1:
            raise ValueError("maximum_single_weight must be in (0, 1]")
        normalized = {
            symbol: min(maximum_single_weight, max(0.0, float(weight)))
            for symbol, weight in target_weights.items()
        }
        if sum(normalized.values()) > 1.0 + 1e-9:
            raise ValueError("target weights exceed 100%")

        starting_order_count = len(self.orders)
        portfolio_value = self.total_value_base
        deltas: Dict[str, float] = {}
        for symbol in set(self.positions) | set(normalized):
            current = self.positions.get(symbol)
            current_value = 0.0 if current is None else current.market_value_base
            deltas[symbol] = normalized.get(symbol, 0.0) * portfolio_value - current_value

        for symbol, delta in sorted(deltas.items(), key=lambda item: item[1]):
            if delta >= 0 or symbol not in quotes:
                continue
            quote = quotes[symbol]
            quantity = math.floor((-delta / quote.fx_to_base) / quote.open)
            self.execute(
                quote,
                OrderSide.SELL,
                quantity,
                cost_schedules.get(quote.security.exchange, CostSchedule()),
            )

        portfolio_value = self.total_value_base
        for symbol, target_weight in sorted(normalized.items(), key=lambda item: item[1], reverse=True):
            quote = quotes.get(symbol)
            if quote is None:
                continue
            current = self.positions.get(symbol)
            current_value = 0.0 if current is None else current.market_value_base
            delta = target_weight * portfolio_value - current_value
            if delta <= quote.open * quote.fx_to_base * quote.lot_size:
                continue
            quantity = math.floor((delta / quote.fx_to_base) / quote.open)
            self.execute(
                quote,
                OrderSide.BUY,
                quantity,
                cost_schedules.get(quote.security.exchange, CostSchedule()),
            )
        return self.orders[starting_order_count:]

    def snapshot(self, trade_date: date) -> PortfolioSnapshot:
        market_value = sum(item.market_value_base for item in self.positions.values())
        total_value = self.cash_base + market_value
        weights = {
            symbol: 0.0 if total_value == 0 else position.market_value_base / total_value
            for symbol, position in self.positions.items()
        }
        return PortfolioSnapshot(
            trade_date=trade_date,
            cash_base=self.cash_base,
            market_value_base=market_value,
            total_value_base=total_value,
            position_weights=weights,
        )
