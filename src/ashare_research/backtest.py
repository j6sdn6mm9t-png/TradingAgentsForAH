"""Daily walk-forward backtest using the production paper-portfolio rules."""

from dataclasses import dataclass
from datetime import date
import math
from statistics import mean, pstdev
from typing import Dict, List, Mapping, Optional

from .market import Exchange
from .portfolio import CostSchedule, OrderResult, PaperPortfolio, PortfolioSnapshot, PriceQuote


@dataclass(frozen=True)
class BacktestMetrics:
    total_return: float
    annualized_return: float
    annualized_volatility: float
    sharpe_ratio: Optional[float]
    maximum_drawdown: float
    turnover: float
    trading_days: int


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: List[PortfolioSnapshot]
    orders: List[OrderResult]
    metrics: BacktestMetrics


class BacktestEngine:
    """Execute target weights on each signal date's open and mark at close.

    Callers must create signals using information available before that open.
    A common daily workflow computes a signal after day T close and stores its
    target weights under the next trading date T+1.
    """

    def __init__(
        self,
        initial_cash: float = 1_000_000.0,
        maximum_single_weight: float = 0.10,
        cost_schedules: Optional[Mapping[Exchange, CostSchedule]] = None,
    ) -> None:
        self.initial_cash = initial_cash
        self.maximum_single_weight = maximum_single_weight
        self.cost_schedules = dict(cost_schedules or {})

    def run(
        self,
        daily_quotes: Mapping[date, Mapping[str, PriceQuote]],
        target_weights: Mapping[date, Mapping[str, float]],
    ) -> BacktestResult:
        if not daily_quotes:
            raise ValueError("daily_quotes cannot be empty")
        portfolio = PaperPortfolio(self.initial_cash)
        curve: List[PortfolioSnapshot] = []
        traded_notional = 0.0
        previous_targets: Dict[str, float] = {}

        for trade_date in sorted(daily_quotes):
            quotes = daily_quotes[trade_date]
            portfolio.start_day(trade_date)
            if trade_date in target_weights:
                previous_targets = dict(target_weights[trade_date])
                before = len(portfolio.orders)
                portfolio.rebalance(
                    previous_targets,
                    quotes,
                    self.cost_schedules,
                    self.maximum_single_weight,
                )
                for order in portfolio.orders[before:]:
                    quote = quotes.get(order.security.symbol)
                    fx = 1.0 if quote is None else quote.fx_to_base
                    traded_notional += order.filled_quantity * order.price_local * fx
            portfolio.mark_to_market(quotes)
            curve.append(portfolio.snapshot(trade_date))

        values = [item.total_value_base for item in curve]
        daily_returns = [values[index] / values[index - 1] - 1 for index in range(1, len(values))]
        total_return = values[-1] / self.initial_cash - 1
        trading_days = len(values)
        annualized_return = (values[-1] / self.initial_cash) ** (252 / max(1, trading_days)) - 1
        volatility = 0.0 if len(daily_returns) < 2 else pstdev(daily_returns) * math.sqrt(252)
        average_return = 0.0 if not daily_returns else mean(daily_returns)
        sharpe = None if volatility == 0 else average_return * 252 / volatility
        peak = values[0]
        maximum_drawdown = 0.0
        for value in values:
            peak = max(peak, value)
            maximum_drawdown = min(maximum_drawdown, value / peak - 1)
        average_nav = mean(values)
        turnover = 0.0 if average_nav == 0 else traded_notional / average_nav
        return BacktestResult(
            equity_curve=curve,
            orders=list(portfolio.orders),
            metrics=BacktestMetrics(
                total_return=total_return,
                annualized_return=annualized_return,
                annualized_volatility=volatility,
                sharpe_ratio=sharpe,
                maximum_drawdown=maximum_drawdown,
                turnover=turnover,
                trading_days=trading_days,
            ),
        )
