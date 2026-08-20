import unittest

from ashare_research.market import Board, Exchange, SecurityId, reference_price_limit


class SecurityIdTests(unittest.TestCase):
    def test_infers_common_exchanges_and_boards(self):
        self.assertEqual(SecurityId.parse("600519").exchange, Exchange.SHANGHAI)
        self.assertEqual(SecurityId.parse("300750").board, Board.CHINEXT)
        self.assertEqual(SecurityId.parse("688981.SH").board, Board.STAR)
        self.assertEqual(SecurityId.parse("830799.BJ").board, Board.BEIJING)
        self.assertEqual(SecurityId.parse("00700.HK").symbol, "00700.HK")
        self.assertEqual(SecurityId.parse("00700").board, Board.HONG_KONG)
        self.assertEqual(SecurityId.parse("700.HK").symbol, "00700.HK")

    def test_rejects_invalid_symbol(self):
        with self.assertRaises(ValueError):
            SecurityId.parse("AAPL")

    def test_reference_limits(self):
        self.assertEqual(reference_price_limit(Board.MAIN, False), 0.10)
        self.assertEqual(reference_price_limit(Board.CHINEXT, False), 0.20)
        self.assertEqual(reference_price_limit(Board.BEIJING, False), 0.30)
        self.assertEqual(reference_price_limit(Board.STAR, True), 0.05)
        self.assertIsNone(reference_price_limit(Board.HONG_KONG, False))


if __name__ == "__main__":
    unittest.main()
