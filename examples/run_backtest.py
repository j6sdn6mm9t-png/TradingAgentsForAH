"""Dependency-free A/H paper-portfolio backtest example."""

from datetime import date, timedelta

from ashare_research.backtest import BacktestEngine
from ashare_research.market import Exchange, SecurityId
from ashare_research.portfolio import CostSchedule, PriceQuote


start = date(2026, 8, 3)
a_share = SecurityId.parse("600519.SH")
hk_share = SecurityId.parse("00700.HK")
quotes = {}
for index in range(15):
    trade_date = start + timedelta(days=index)
    quotes[trade_date] = {
        a_share.symbol: PriceQuote(
            a_share,
            trade_date,
            open=1450 + index * 3,
            close=1454 + index * 3,
            lot_size=100,
        ),
        hk_share.symbol: PriceQuote(
            hk_share,
            trade_date,
            open=560 + index * 1.5,
            close=562 + index * 1.5,
            lot_size=100,
            currency="HKD",
            fx_to_base=0.92,
        ),
    }

costs = {
    # Example parameters only. Production costs must be effective-date versioned.
    Exchange.SHANGHAI: CostSchedule(commission_rate=0.0003, minimum_commission=5),
    Exchange.HONG_KONG: CostSchedule(commission_rate=0.0003),
}
result = BacktestEngine(
    initial_cash=1_000_000,
    maximum_single_weight=0.25,
    cost_schedules=costs,
).run(
    quotes,
    {start: {a_share.symbol: 0.20, hk_share.symbol: 0.20}},
)

print("total_return", f"{result.metrics.total_return:.2%}")
print("maximum_drawdown", f"{result.metrics.maximum_drawdown:.2%}")
print("turnover", f"{result.metrics.turnover:.2f}x")
print("orders", len(result.orders))
