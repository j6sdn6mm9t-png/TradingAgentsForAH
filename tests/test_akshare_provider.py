import unittest
from datetime import date, timedelta

from ashare_research.data.akshare_provider import AkShareDataProvider
from ashare_research.market import SecurityId


class FakeFrame:
    def __init__(self, records):
        self.records = records

    def to_dict(self, orient):
        if orient != "records":
            raise AssertionError("unexpected orient")
        return self.records


class FakeAkShare:
    def _prices(self):
        start = date(2026, 5, 1)
        return FakeFrame(
            [
                {
                    "日期": start + timedelta(days=index),
                    "收盘": 10 + index * 0.1,
                    "成交量": 1000 + index,
                }
                for index in range(100)
            ]
        )

    def stock_zh_a_hist(self, **kwargs):
        return self._prices()

    def stock_hk_hist(self, **kwargs):
        return self._prices()

    def stock_individual_info_em(self, **kwargs):
        return FakeFrame(
            [
                {"item": "股票简称", "value": "测试公司"},
                {"item": "行业", "value": "测试行业"},
            ]
        )

    def stock_hk_company_profile_em(self, **kwargs):
        return FakeFrame([{"公司名称": "测试港股", "所属行业": "互联网"}])

    def stock_financial_analysis_indicator_em(self, **kwargs):
        return FakeFrame(
            [
                {
                    "REPORT_DATE": date.today(),
                    "ROEJQ": 18.0,
                    "TOTALOPERATEREVETZ": 12.0,
                    "PARENTNETPROFITTZ": 15.0,
                    "ZCFZL": 35.0,
                }
            ]
        )

    def stock_zh_valuation_comparison_em(self, **kwargs):
        return FakeFrame(
            [{"代码": "600000", "市盈率-TTM": 12.5, "市净率-MRQ": 1.2}]
        )

    def stock_hk_financial_indicator_em(self, **kwargs):
        return FakeFrame(
            [
                {
                    "市盈率": 20.0,
                    "市净率": 3.5,
                    "股东权益回报率(%)": 22.0,
                    "营业总收入滚动环比增长(%)": 8.0,
                    "净利润滚动环比增长(%)": 11.0,
                }
            ]
        )


class AkShareProviderTests(unittest.TestCase):
    def test_builds_a_share_price_snapshot(self):
        provider = AkShareDataProvider(FakeAkShare())
        snapshot = provider.get_snapshot(SecurityId.parse("600000.SH"), date(2026, 8, 18))
        self.assertEqual(snapshot.name, "测试公司")
        self.assertGreater(snapshot.return_60d, 0)
        self.assertIsNone(snapshot.roe)
        self.assertEqual(len(provider.get_evidence(snapshot.security, date(2026, 8, 18))), 1)

    def test_builds_hong_kong_price_snapshot(self):
        provider = AkShareDataProvider(FakeAkShare())
        snapshot = provider.get_snapshot(SecurityId.parse("00700.HK"), date(2026, 8, 18))
        self.assertEqual(snapshot.security.symbol, "00700.HK")
        self.assertEqual(snapshot.industry, "互联网")

    def test_current_research_adds_a_share_fundamentals_and_valuation(self):
        provider = AkShareDataProvider(FakeAkShare())
        snapshot = provider.get_snapshot(SecurityId.parse("600000.SH"), date.today())
        self.assertEqual(snapshot.roe, 0.18)
        self.assertEqual(snapshot.pe_ttm, 12.5)
        evidence = provider.get_evidence(snapshot.security, date.today())
        self.assertTrue(any(item.category == "fundamental" for item in evidence))
        self.assertTrue(any(item.category == "valuation" for item in evidence))

    def test_current_research_adds_hong_kong_fundamentals(self):
        provider = AkShareDataProvider(FakeAkShare())
        snapshot = provider.get_snapshot(SecurityId.parse("00700.HK"), date.today())
        self.assertEqual(snapshot.name, "测试港股")
        self.assertEqual(snapshot.roe, 0.22)
        self.assertEqual(snapshot.pe_ttm, 20.0)

    def test_hong_kong_price_uses_sina_endpoint_when_available(self):
        class FallbackAkShare(FakeAkShare):
            def stock_hk_hist(self, **kwargs):
                raise RuntimeError("primary endpoint unavailable")

            def stock_hk_daily(self, **kwargs):
                return self._prices()

        provider = AkShareDataProvider(FallbackAkShare())
        snapshot = provider.get_snapshot(
            SecurityId.parse("00700.HK"), date(2026, 8, 8)
        )
        self.assertGreater(snapshot.return_60d, 0)

    def test_a_share_uses_alternate_sources_when_eastmoney_research_is_invalid(self):
        class FallbackAkShare(FakeAkShare):
            def stock_zh_a_hist(self, **kwargs):
                raise RuntimeError("eastmoney price blocked")

            def stock_zh_a_hist_tx(self, **kwargs):
                return self._prices()

            def stock_individual_info_em(self, **kwargs):
                raise RuntimeError("eastmoney profile blocked")

            def stock_profile_cninfo(self, **kwargs):
                return FakeFrame(
                    [
                        {
                            "公司名称": "测试股份有限公司",
                            "A股简称": "测试股份",
                            "所属行业": "测试行业",
                        }
                    ]
                )

            def stock_financial_analysis_indicator_em(self, **kwargs):
                return FakeFrame([{"REPORT_DATE": date(2026, 6, 30), "OTHER": 1}])

            def stock_financial_analysis_indicator(self, **kwargs):
                return FakeFrame(
                    [
                        {
                            "日期": date(2026, 6, 30),
                            "摊薄每股收益(元)": 4.0,
                            "每股净资产_调整前(元)": 20.0,
                            "加权净资产收益率(%)": 10.0,
                            "主营业务收入增长率(%)": 5.0,
                            "净利润增长率(%)": 6.0,
                            "资产负债率(%)": 40.0,
                        },
                        {"日期": date(2025, 12, 31), "摊薄每股收益(元)": 7.0},
                        {"日期": date(2025, 6, 30), "摊薄每股收益(元)": 3.0},
                    ]
                )

            def stock_zh_valuation_comparison_em(self, **kwargs):
                return FakeFrame([{"代码": "600000", "OTHER": 1}])

        provider = AkShareDataProvider(FallbackAkShare())
        snapshot = provider.get_snapshot(SecurityId.parse("600000.SH"), date.today())
        self.assertEqual(snapshot.name, "测试股份")
        self.assertEqual(snapshot.roe, 0.10)
        self.assertAlmostEqual(snapshot.pe_ttm, snapshot.close / 8.0)
        self.assertAlmostEqual(snapshot.pb, snapshot.close / 20.0)
        evidence = provider.get_evidence(snapshot.security, date.today())
        market = next(item for item in evidence if item.category == "market")
        quality = next(item for item in evidence if item.category == "data_quality")
        self.assertEqual(market.source, "AkShare / 腾讯证券")
        self.assertIn("东方财富A股财务指标失败", quality.content)
        self.assertTrue(any(item.category == "fundamental" for item in evidence))
        self.assertTrue(any(item.category == "valuation" for item in evidence))


if __name__ == "__main__":
    unittest.main()
