"""AkShare adapter for current A/H prices, fundamentals, and valuation.

Historical research intentionally leaves non-point-in-time fundamentals empty until
a filing-date-aware provider is configured. This prevents a current financial
snapshot from leaking into historical research.
"""

from datetime import date, timedelta
import math
from typing import Any, Dict, List, Optional, Tuple

from ..domain import Evidence, MarketSnapshot, ValuationContext
from ..market import Exchange, SecurityId


def _value(record: Dict[str, Any], *names: str) -> Any:
    for name in names:
        if name in record:
            return record[name]
    raise KeyError(f"none of the columns are present: {names}")


def _as_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value).split(" ", 1)[0].replace("/", "-")
    return date.fromisoformat(text)


def _number(record: Dict[str, Any], *names: str, percent: bool = False) -> Optional[float]:
    for name in names:
        if name not in record:
            continue
        value = record[name]
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isnan(number) or math.isinf(number):
            continue
        return number / 100 if percent else number
    return None


def _error_summary(error: Exception, limit: int = 240) -> str:
    """Keep endpoint diagnostics useful without dumping an entire request URL."""

    message = " ".join(str(error).split()) or "no error message"
    if len(message) > limit:
        message = message[: limit - 3] + "..."
    return f"{type(error).__name__}: {message}"


class AkShareDataProvider:
    """Fetch one security at a time from AkShare with a small in-process cache."""

    name = "akshare"

    def __init__(self, ak_module: Optional[Any] = None, lookback_days: int = 180) -> None:
        if ak_module is None:
            try:
                import akshare as ak_module  # type: ignore[no-redef]
            except ImportError as exc:
                raise RuntimeError(
                    "AkShare is not installed. Run `python3 -m pip install -e '.[akshare]'`."
                ) from exc
        self.ak = ak_module
        self.lookback_days = max(120, lookback_days)
        self._cache: Dict[Tuple[str, date], Tuple[MarketSnapshot, List[Evidence]]] = {}

    def _prepare_history_records(
        self, frame: Any, security: SecurityId, as_of: date
    ) -> List[Dict[str, Any]]:
        records = frame.to_dict("records")
        records = [
            record
            for record in records
            if as_of - timedelta(days=self.lookback_days)
            <= _as_date(_value(record, "日期", "date"))
            <= as_of
        ]
        records.sort(key=lambda record: _as_date(_value(record, "日期", "date")))
        if len(records) < 61:
            raise ValueError(
                f"returned only {len(records)} daily rows for {security.symbol}; "
                "at least 61 are required"
            )
        return records

    def _history_records(
        self, security: SecurityId, as_of: date
    ) -> Tuple[List[Dict[str, Any]], str, List[str]]:
        start_date = (as_of - timedelta(days=self.lookback_days)).strftime("%Y%m%d")
        end_date = as_of.strftime("%Y%m%d")
        endpoints = []
        if security.exchange == Exchange.HONG_KONG:
            if hasattr(self.ak, "stock_hk_daily"):
                endpoints.append(
                    (
                        "新浪港股日线",
                        "AkShare / 新浪财经",
                        lambda: self.ak.stock_hk_daily(
                            symbol=security.code,
                            adjust="qfq",
                        ),
                    )
                )
            endpoints.append(
                (
                    "东方财富港股日线",
                    "AkShare / 东方财富",
                    lambda: self.ak.stock_hk_hist(
                        symbol=security.code,
                        period="daily",
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq",
                    ),
                )
            )
        else:
            vendor_symbol = f"{security.exchange.value.lower()}{security.code}"
            if security.exchange != Exchange.BEIJING and hasattr(
                self.ak, "stock_zh_a_hist_tx"
            ):
                endpoints.append(
                    (
                        "腾讯A股日线",
                        "AkShare / 腾讯证券",
                        lambda: self.ak.stock_zh_a_hist_tx(
                            symbol=vendor_symbol,
                            start_date=start_date,
                            end_date=end_date,
                            adjust="qfq",
                            timeout=15,
                        ),
                    )
                )
            endpoints.append(
                (
                    "东方财富A股日线",
                    "AkShare / 东方财富",
                    lambda: self.ak.stock_zh_a_hist(
                        symbol=security.code,
                        period="daily",
                        start_date=start_date,
                        end_date=end_date,
                        adjust="qfq",
                        timeout=15,
                    ),
                )
            )
            if security.exchange != Exchange.BEIJING and hasattr(
                self.ak, "stock_zh_a_daily"
            ):
                endpoints.append(
                    (
                        "新浪A股日线",
                        "AkShare / 新浪财经",
                        lambda: self.ak.stock_zh_a_daily(
                            symbol=vendor_symbol,
                            start_date=start_date,
                            end_date=end_date,
                            adjust="qfq",
                        ),
                    )
                )

        failures: List[str] = []
        for endpoint_name, source, fetch in endpoints:
            try:
                records = self._prepare_history_records(fetch(), security, as_of)
                return records, source, failures
            except Exception as error:
                failures.append(f"{endpoint_name}失败（{_error_summary(error)}）")
        raise RuntimeError(
            f"AkShare 无法获取 {security.symbol} 的有效日线：" + "；".join(failures)
        )

    def _a_share_metadata(
        self, security: SecurityId
    ) -> Tuple[str, str, List[str]]:
        failures: List[str] = []
        if hasattr(self.ak, "stock_profile_cninfo"):
            try:
                frame = self.ak.stock_profile_cninfo(symbol=security.code)
                records = frame.to_dict("records")
                if not records:
                    raise ValueError("returned no company profile")
                record = records[0]
                name = str(
                    record.get("A股简称") or record.get("公司名称") or security.symbol
                )
                industry = str(record.get("所属行业") or "未知")
                if name == security.symbol and industry == "未知":
                    raise ValueError("returned no supported company profile fields")
                return (
                    name,
                    industry,
                    failures,
                )
            except Exception as error:
                failures.append(f"巨潮公司资料失败（{_error_summary(error)}）")
        try:
            frame = self.ak.stock_individual_info_em(symbol=security.code, timeout=15)
            values = {
                str(record.get("item")): record.get("value")
                for record in frame.to_dict("records")
            }
            name = str(values.get("股票简称") or security.symbol)
            industry = str(values.get("行业") or "未知")
            if name == security.symbol and industry == "未知":
                raise ValueError("returned no supported company profile fields")
            return (
                name,
                industry,
                failures,
            )
        except Exception as error:
            failures.append(f"东方财富公司资料失败（{_error_summary(error)}）")
        return security.symbol, "未知", failures

    def _hk_metadata(self, security: SecurityId) -> Tuple[str, str, List[str]]:
        try:
            frame = self.ak.stock_hk_company_profile_em(symbol=security.code)
            records = frame.to_dict("records")
            if not records:
                raise ValueError("returned no company profile")
            record = records[0]
            name = str(record.get("公司名称") or security.symbol)
            industry = str(record.get("所属行业") or "未知")
            if name == security.symbol and industry == "未知":
                raise ValueError("returned no supported company profile fields")
            return (
                name,
                industry,
                [],
            )
        except Exception as error:
            return (
                security.symbol,
                "未知",
                [f"东方财富港股公司资料失败（{_error_summary(error)}）"],
            )

    @staticmethod
    def _sina_ttm_eps(
        records: List[Dict[str, Any]], latest: Dict[str, Any]
    ) -> Optional[float]:
        report_date = _as_date(latest["日期"])
        current_eps = _number(latest, "摊薄每股收益(元)", "加权每股收益(元)")
        if current_eps is None:
            return None
        if report_date.month == 12:
            return current_eps
        by_date = {_as_date(record["日期"]): record for record in records}
        try:
            prior_period_date = report_date.replace(year=report_date.year - 1)
        except ValueError:
            return None
        prior_annual = by_date.get(date(report_date.year - 1, 12, 31))
        prior_period = by_date.get(prior_period_date)
        if prior_annual is None or prior_period is None:
            return None
        prior_annual_eps = _number(
            prior_annual, "摊薄每股收益(元)", "加权每股收益(元)"
        )
        prior_period_eps = _number(
            prior_period, "摊薄每股收益(元)", "加权每股收益(元)"
        )
        if prior_annual_eps is None or prior_period_eps is None:
            return None
        return current_eps + prior_annual_eps - prior_period_eps

    def _sina_financial_records(
        self, security: SecurityId, as_of: date
    ) -> List[Dict[str, Any]]:
        frame = self.ak.stock_financial_analysis_indicator(
            symbol=security.code, start_year=str(max(1900, as_of.year - 2))
        )
        records = [
            record
            for record in frame.to_dict("records")
            if _as_date(record["日期"]) <= as_of
        ]
        records.sort(key=lambda item: _as_date(item["日期"]), reverse=True)
        if not records:
            raise ValueError("returned no financial record on or before research date")
        return records

    def _a_share_current_research(
        self, security: SecurityId, as_of: date, close: float
    ) -> Tuple[Dict[str, Any], List[Evidence], List[str]]:
        metrics: Dict[str, Any] = {}
        evidence: List[Evidence] = []
        limitations: List[str] = []
        sina_records: Optional[List[Dict[str, Any]]] = None
        try:
            frame = self.ak.stock_financial_analysis_indicator_em(
                symbol=security.symbol, indicator="按报告期"
            )
            records = [
                record
                for record in frame.to_dict("records")
                if _as_date(record["REPORT_DATE"]) <= as_of
            ]
            records.sort(key=lambda item: _as_date(item["REPORT_DATE"]), reverse=True)
            if not records:
                raise ValueError("no financial record on or before research date")
            latest = records[0]
            report_date = _as_date(latest["REPORT_DATE"])
            metrics["_name"] = str(
                latest.get("SECURITY_NAME_ABBR") or security.symbol
            )
            metrics.update(
                roe=_number(latest, "ROEJQ", "ROEKCJQ", percent=True),
                revenue_growth=_number(latest, "TOTALOPERATEREVETZ", percent=True),
                profit_growth=_number(
                    latest, "PARENTNETPROFITTZ", "KCFJCXSYJLRTZ", percent=True
                ),
                debt_ratio=_number(latest, "ZCFZL", percent=True),
            )
            if all(
                metrics.get(key) is None
                for key in ("roe", "revenue_growth", "profit_growth", "debt_ratio")
            ):
                raise ValueError("latest record has no supported financial fields")
            evidence.append(
                Evidence(
                    evidence_id=f"akshare-financial-{security.symbol}-{report_date.isoformat()}",
                    source="AkShare / 东方财富",
                    title=f"{security.symbol} 最新主要财务指标",
                    observed_at=as_of,
                    published_at=as_of,
                    content=(
                        f"报告期 {report_date.isoformat()}；"
                        f"ROE {metrics['roe']!r}，营收同比 {metrics['revenue_growth']!r}，"
                        f"归母净利润同比 {metrics['profit_growth']!r}，"
                        f"资产负债率 {metrics['debt_ratio']!r}。"
                        "接口未提供原始公告发布时间，仅限当日研究使用。"
                    ),
                    url="https://akshare.akfamily.xyz/data/stock/stock.html",
                    category="fundamental",
                    source_tier="aggregator",
                    point_in_time=False,
                )
            )
        except Exception as error:
            limitations.append(f"东方财富A股财务指标失败（{_error_summary(error)}）")
            try:
                sina_records = self._sina_financial_records(security, as_of)
                latest = sina_records[0]
                report_date = _as_date(latest["日期"])
                metrics.update(
                    roe=_number(
                        latest,
                        "加权净资产收益率(%)",
                        "净资产收益率(%)",
                        percent=True,
                    ),
                    revenue_growth=_number(
                        latest, "主营业务收入增长率(%)", percent=True
                    ),
                    profit_growth=_number(latest, "净利润增长率(%)", percent=True),
                    debt_ratio=_number(latest, "资产负债率(%)", percent=True),
                )
                if all(
                    metrics.get(key) is None
                    for key in ("roe", "revenue_growth", "profit_growth", "debt_ratio")
                ):
                    raise ValueError("latest record has no supported financial fields")
                evidence.append(
                    Evidence(
                        evidence_id=(
                            f"akshare-financial-{security.symbol}-{report_date.isoformat()}"
                        ),
                        source="AkShare / 新浪财经",
                        title=f"{security.symbol} 最新主要财务指标（备用源）",
                        observed_at=as_of,
                        published_at=as_of,
                        content=(
                            f"报告期 {report_date.isoformat()}；"
                            f"ROE {metrics['roe']!r}，"
                            f"营收同比 {metrics['revenue_growth']!r}，"
                            f"净利润同比 {metrics['profit_growth']!r}，"
                            f"资产负债率 {metrics['debt_ratio']!r}。"
                            "接口未提供原始公告发布时间，仅限当日研究使用。"
                        ),
                        url="https://akshare.akfamily.xyz/data/stock/stock.html",
                        category="fundamental",
                        source_tier="aggregator",
                        point_in_time=False,
                    )
                )
            except Exception as fallback_error:
                limitations.append(
                    f"新浪A股财务指标失败（{_error_summary(fallback_error)}）"
                )

        try:
            vendor_symbol = f"{security.exchange.value}{security.code}"
            frame = self.ak.stock_zh_valuation_comparison_em(symbol=vendor_symbol)
            records = frame.to_dict("records")
            selected = next(
                (item for item in records if str(item.get("代码")) == security.code),
                None,
            )
            if selected is None:
                raise ValueError("no valuation record for requested security")
            pe = _number(selected, "市盈率-TTM")
            pb = _number(selected, "市净率-MRQ")
            metrics["pe_ttm"] = pe if pe is not None and pe > 0 else None
            metrics["pb"] = pb if pb is not None and pb > 0 else None
            if metrics["pe_ttm"] is None and metrics["pb"] is None:
                raise ValueError("record has no supported positive valuation fields")
            evidence.append(
                Evidence(
                    evidence_id=f"akshare-valuation-{security.symbol}-{as_of.isoformat()}",
                    source="AkShare / 东方财富",
                    title=f"{security.symbol} 聚合接口当前估值快照",
                    observed_at=as_of,
                    published_at=as_of,
                    content=f"PE-TTM {metrics['pe_ttm']!r}，PB-MRQ {metrics['pb']!r}。",
                    url="https://akshare.akfamily.xyz/data/stock/stock.html",
                    category="valuation",
                    source_tier="aggregator",
                    point_in_time=False,
                )
            )
        except Exception as error:
            limitations.append(f"东方财富A股估值失败（{_error_summary(error)}）")
            try:
                if sina_records is None:
                    sina_records = self._sina_financial_records(security, as_of)
                latest = sina_records[0]
                report_date = _as_date(latest["日期"])
                ttm_eps = self._sina_ttm_eps(sina_records, latest)
                book_value = _number(
                    latest, "每股净资产_调整前(元)", "每股净资产_调整后(元)"
                )
                pe = close / ttm_eps if ttm_eps is not None and ttm_eps > 0 else None
                pb = close / book_value if book_value is not None and book_value > 0 else None
                if pe is None and pb is None:
                    raise ValueError("insufficient per-share fields for derived valuation")
                metrics["pe_ttm"] = pe
                metrics["pb"] = pb
                evidence.append(
                    Evidence(
                        evidence_id=f"akshare-valuation-{security.symbol}-{as_of.isoformat()}",
                        source="AkShare / 新浪财经",
                        title=f"{security.symbol} 当前估值（备用源推导）",
                        observed_at=as_of,
                        published_at=as_of,
                        content=(
                            f"按收盘价 {close:.4f} 与 {report_date.isoformat()} "
                            "最新财务字段推导；"
                            f"PE-TTM {pe!r}，PB {pb!r}。"
                        ),
                        url="https://akshare.akfamily.xyz/data/stock/stock.html",
                        category="valuation",
                        source_tier="aggregator",
                        point_in_time=False,
                    )
                )
            except Exception as fallback_error:
                error_text = _error_summary(fallback_error)
                limitations.append(f"新浪财务字段无法推导当前估值（{error_text}）")
        return metrics, evidence, limitations

    def _hk_current_research(
        self, security: SecurityId, as_of: date
    ) -> Tuple[Dict[str, Any], List[Evidence], List[str]]:
        metrics: Dict[str, Any] = {}
        evidence: List[Evidence] = []
        limitations: List[str] = []
        try:
            frame = self.ak.stock_hk_financial_indicator_em(symbol=security.code)
            records = frame.to_dict("records")
            if not records:
                raise ValueError("no Hong Kong financial indicator record")
            latest = records[0]
            pe = _number(latest, "市盈率")
            pb = _number(latest, "市净率")
            metrics.update(
                pe_ttm=pe if pe is not None and pe > 0 else None,
                pb=pb if pb is not None and pb > 0 else None,
                roe=_number(latest, "股东权益回报率(%)", percent=True),
                revenue_growth=_number(
                    latest, "营业总收入滚动环比增长(%)", percent=True
                ),
                profit_growth=_number(latest, "净利润滚动环比增长(%)", percent=True),
                debt_ratio=None,
            )
            if all(
                metrics.get(key) is None
                for key in ("pe_ttm", "pb", "roe", "revenue_growth", "profit_growth")
            ):
                raise ValueError("record has no supported financial or valuation fields")
            evidence.append(
                Evidence(
                    evidence_id=f"akshare-financial-{security.symbol}-{as_of.isoformat()}",
                    source="AkShare / 东方财富",
                    title=f"{security.symbol} 港股核心财务与估值指标",
                    observed_at=as_of,
                    published_at=as_of,
                    content=(
                        f"PE {metrics['pe_ttm']!r}，PB {metrics['pb']!r}，"
                        f"ROE {metrics['roe']!r}，"
                        f"收入滚动环比 {metrics['revenue_growth']!r}，"
                        f"利润滚动环比 {metrics['profit_growth']!r}。"
                        "接口未提供原始公告发布时间，仅限当日研究使用。"
                    ),
                    url="https://akshare.akfamily.xyz/data/stock/stock.html",
                    category="fundamental_valuation",
                    source_tier="aggregator",
                    point_in_time=False,
                )
            )
        except Exception as error:
            limitations.append(
                f"东方财富港股核心财务与估值失败（{_error_summary(error)}）"
            )
        return metrics, evidence, limitations

    def _load(self, security: SecurityId, as_of: date) -> Tuple[MarketSnapshot, List[Evidence]]:
        cache_key = (security.symbol, as_of)
        if cache_key in self._cache:
            return self._cache[cache_key]

        records, price_source, limitations = self._history_records(security, as_of)
        closes = [float(_value(record, "收盘", "close")) for record in records]
        volumes = [float(_value(record, "成交量", "volume")) for record in records]
        last = records[-1]
        last_date = _as_date(_value(last, "日期", "date"))
        close = closes[-1]
        ma20 = sum(closes[-20:]) / 20
        average_volume = sum(volumes[-20:]) / 20
        name, industry, metadata_limitations = (
            self._hk_metadata(security)
            if security.exchange == Exchange.HONG_KONG
            else self._a_share_metadata(security)
        )
        limitations.extend(metadata_limitations)
        research_metrics: Dict[str, Any] = {}
        research_evidence: List[Evidence] = []
        if as_of == date.today():
            if security.exchange == Exchange.HONG_KONG:
                research_metrics, research_evidence, research_limitations = (
                    self._hk_current_research(security, as_of)
                )
            else:
                research_metrics, research_evidence, research_limitations = (
                    self._a_share_current_research(security, as_of, close)
                )
            limitations.extend(research_limitations)
        if name == security.symbol and research_metrics.get("_name"):
            name = str(research_metrics["_name"])
        snapshot = MarketSnapshot(
            security=security,
            as_of=last_date,
            name=name,
            industry=industry,
            close=close,
            return_20d=close / closes[-21] - 1,
            return_60d=close / closes[-61] - 1,
            ma20_gap=close / ma20 - 1,
            volume_ratio=0.0 if average_volume == 0 else volumes[-1] / average_volume,
            pe_ttm=research_metrics.get("pe_ttm"),
            pb=research_metrics.get("pb"),
            roe=research_metrics.get("roe"),
            revenue_growth=research_metrics.get("revenue_growth"),
            profit_growth=research_metrics.get("profit_growth"),
            debt_ratio=research_metrics.get("debt_ratio"),
            capital_flow_score=0.0,
            news_sentiment=0.0,
            is_st=name.upper().startswith(("ST", "*ST")),
            suspended=False,
            days_since_market_data=(as_of - last_date).days,
        )
        evidence = [
            Evidence(
                evidence_id=f"akshare-price-{security.symbol}-{last_date.isoformat()}",
                source=price_source,
                title=f"{security.symbol} 前复权日线快照",
                observed_at=as_of,
                published_at=last_date,
                content=(
                    f"截至 {last_date.isoformat()} 共获取 {len(records)} 条日线；"
                    f"收盘 {close:.3f}，20 日收益 {snapshot.return_20d:.2%}，"
                    f"60 日收益 {snapshot.return_60d:.2%}。"
                    + (
                        "当日财务与估值另见对应 evidence；"
                        "公告仍需法披来源检索。"
                        if research_evidence
                        else (
                            "该研究日未使用无发布时间校验的财务与估值；"
                            "公告需另行检索。"
                        )
                    )
                ),
                url="https://akshare.akfamily.xyz/data/stock/stock.html",
                category="market",
                source_tier="aggregator",
                point_in_time=True,
            )
        ]
        evidence.extend(research_evidence)
        if limitations:
            evidence.append(
                Evidence(
                    evidence_id=f"akshare-limitations-{security.symbol}-{as_of.isoformat()}",
                    source="system",
                    title="本次数据源降级与缺口",
                    observed_at=as_of,
                    published_at=as_of,
                    content=(
                        "；".join(limitations)
                        + "；公告仍需从交易所/法披网站检索。"
                    ),
                    category="data_quality",
                    source_tier="system",
                    point_in_time=True,
                )
            )
        self._cache[cache_key] = snapshot, evidence
        return snapshot, evidence

    def get_snapshot(self, security: SecurityId, as_of: date) -> MarketSnapshot:
        return self._load(security, as_of)[0]

    def get_evidence(self, security: SecurityId, as_of: date) -> List[Evidence]:
        return list(self._load(security, as_of)[1])

    def get_valuation_context(
        self, security: SecurityId, as_of: date
    ) -> ValuationContext:
        # AkShare snapshots do not contain auditable forward scenarios. The research
        # layer must build them from filings, forecasts, and explicit assumptions.
        return ValuationContext()
