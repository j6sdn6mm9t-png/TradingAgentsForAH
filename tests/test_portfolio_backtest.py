import unittest
from datetime import date, timedelta

from ashare_research.backtest import BacktestEngine
from ashare_research.market import Exchange, SecurityId
from ashare_research.portfolio import (
    CostSchedule,
    OrderSide,
    OrderStatus,
    PaperPortfolio,
    PriceQuote,
)


class PortfolioTests(unittest.TestCase):
    def setUp(self):
        self.a_security = SecurityId.parse("600519.SH")
        self.hk_security = SecurityId.parse("00700.HK")

    def test_a_share_t_plus_one_blocks_same_day_sale(self):
        trade_date = date(2026, 8, 18)
        quote = PriceQuote(self.a_security, trade_date, open=100, close=102)
        portfolio = PaperPortfolio(100_000)
        portfolio.start_day(trade_date)
        buy = portfolio.execute(quote, OrderSide.BUY, 500, CostSchedule())
        sell = portfolio.execute(quote, OrderSide.SELL, 500, CostSchedule())
        self.assertEqual(buy.status, OrderStatus.FILLED)
        self.assertEqual(sell.status, OrderStatus.REJECTED)
        self.assertIn("T+1", sell.reason)

        next_date = trade_date + timedelta(days=1)
        next_quote = PriceQuote(self.a_security, next_date, open=103, close=104)
        portfolio.start_day(next_date)
        sell_next_day = portfolio.execute(next_quote, OrderSide.SELL, 500, CostSchedule())
        self.assertEqual(sell_next_day.status, OrderStatus.FILLED)

    def test_hong_kong_board_lot_and_fx(self):
        trade_date = date(2026, 8, 18)
        quote = PriceQuote(
            self.hk_security,
            trade_date,
            open=500,
            close=510,
            lot_size=100,
            currency="HKD",
            fx_to_base=0.92,
        )
        portfolio = PaperPortfolio(100_000)
        portfolio.start_day(trade_date)
        result = portfolio.execute(quote, OrderSide.BUY, 150, CostSchedule())
        self.assertEqual(result.filled_quantity, 100)
        self.assertAlmostEqual(portfolio.positions["00700.HK"].market_value_base, 46_000)


class BacktestTests(unittest.TestCase):
    def test_walk_forward_curve_and_metrics(self):
        security = SecurityId.parse("600519.SH")
        start = date(2026, 8, 17)
        quotes = {}
        for index in range(5):
            trade_date = start + timedelta(days=index)
            quotes[trade_date] = {
                security.symbol: PriceQuote(
                    security,
                    trade_date,
                    open=100 + index,
                    close=101 + index,
                )
            }
        result = BacktestEngine(
            initial_cash=100_000,
            maximum_single_weight=0.5,
            cost_schedules={Exchange.SHANGHAI: CostSchedule()},
        ).run(quotes, {start: {security.symbol: 0.5}})
        self.assertEqual(len(result.equity_curve), 5)
        self.assertGreater(result.metrics.total_return, 0)
        self.assertGreater(result.metrics.turnover, 0)
        self.assertEqual(result.metrics.trading_days, 5)


if __name__ == "__main__":
    unittest.main()
