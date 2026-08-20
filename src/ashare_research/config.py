"""Configuration for evidence collection and report output."""

from dataclasses import dataclass
import os
@dataclass(frozen=True)
class ResearchConfig:
    provider: str = "demo"
    stale_after_days: int = 7
    report_dir: str = "reports"

    @classmethod
    def from_env(cls) -> "ResearchConfig":
        return cls(
            provider=os.getenv("ASHARE_PROVIDER", "demo"),
            stale_after_days=int(os.getenv("ASHARE_STALE_AFTER_DAYS", "7")),
            report_dir=os.getenv("ASHARE_REPORT_DIR", "reports"),
        )

    def __post_init__(self) -> None:
        if self.stale_after_days < 0:
            raise ValueError("stale_after_days must be non-negative")
