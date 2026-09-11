from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Availability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class Severity(str, Enum):
    HEALTHY = "healthy"
    CHECK = "check"
    ATTENTION = "attention"
    IMPORTANT = "important"


class CheckState(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


@dataclass
class DiagnosticResult:
    title: str
    score: int
    coverage: int | None = None
    facts: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    note: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "score": self.score,
            "coverage": self.coverage,
            "facts": list(self.facts),
            "issues": list(self.issues),
            "actions": list(self.actions),
            "note": self.note,
            **self.extra,
        }
