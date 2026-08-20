"""A-share security identifiers and versionable market-rule helpers."""

from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional


class Exchange(str, Enum):
    SHANGHAI = "SH"
    SHENZHEN = "SZ"
    BEIJING = "BJ"
    HONG_KONG = "HK"


class Board(str, Enum):
    MAIN = "main"
    STAR = "star"
    CHINEXT = "chinext"
    BEIJING = "beijing"
    HONG_KONG = "hong_kong"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SecurityId:
    code: str
    exchange: Exchange

    @property
    def symbol(self) -> str:
        return f"{self.code}.{self.exchange.value}"

    @property
    def board(self) -> Board:
        if self.exchange == Exchange.HONG_KONG:
            return Board.HONG_KONG
        if self.exchange == Exchange.BEIJING:
            return Board.BEIJING
        if self.exchange == Exchange.SHANGHAI and self.code.startswith("688"):
            return Board.STAR
        if self.exchange == Exchange.SHENZHEN and self.code.startswith(("300", "301")):
            return Board.CHINEXT
        if self.code.startswith(("000", "001", "002", "003", "600", "601", "603", "605")):
            return Board.MAIN
        return Board.UNKNOWN

    @classmethod
    def parse(cls, value: str) -> "SecurityId":
        normalized = (
            value.strip()
            .upper()
            .replace("XSHG", "SH")
            .replace("XSHE", "SZ")
            .replace("XHKG", "HK")
        )
        match = re.fullmatch(r"(\d{1,6})(?:[.\-]?(SH|SZ|BJ|HK))?", normalized)
        if not match:
            raise ValueError(f"invalid A/H-share security identifier: {value!r}")
        code, suffix = match.groups()
        if suffix == Exchange.HONG_KONG.value:
            if len(code) > 5:
                raise ValueError(f"invalid Hong Kong security identifier: {value!r}")
            code = code.zfill(5)
        elif suffix is not None and len(code) != 6:
            raise ValueError(f"mainland security code must contain 6 digits: {value!r}")
        elif suffix is None and len(code) == 5:
            suffix = Exchange.HONG_KONG.value
        elif suffix is None and len(code) != 6:
            raise ValueError(
                "ambiguous short code; provide a 5-digit Hong Kong code or an exchange suffix"
            )
        exchange = Exchange(suffix) if suffix else infer_exchange(code)
        return cls(code=code, exchange=exchange)


def infer_exchange(code: str) -> Exchange:
    if code.startswith(("4", "8", "92")):
        return Exchange.BEIJING
    if code.startswith(("5", "6", "9")):
        return Exchange.SHANGHAI
    if code.startswith(("0", "1", "2", "3")):
        return Exchange.SHENZHEN
    raise ValueError(f"cannot infer exchange for code {code!r}; provide an explicit suffix")


def reference_price_limit(board: Board, is_st: bool) -> Optional[float]:
    """Return a reference limit percentage, not an execution-grade rule decision.

    Listing-day exceptions and rule changes require a date-versioned production rule engine.
    """
    if board == Board.HONG_KONG:
        return None
    if is_st:
        return 0.05
    return {Board.STAR: 0.20, Board.CHINEXT: 0.20, Board.BEIJING: 0.30}.get(board, 0.10)
