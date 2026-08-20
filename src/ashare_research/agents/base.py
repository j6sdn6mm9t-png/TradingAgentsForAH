from abc import ABC, abstractmethod

from ..domain import AnalystReport, ResearchState


def clamp(value: float, lower: float = -1.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


class Analyst(ABC):
    role: str

    @abstractmethod
    def analyze(self, state: ResearchState) -> AnalystReport:
        raise NotImplementedError
