from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Availability(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


class Severity(str, Enum):
    HEALTHY = "healthy"
    CHECK = "check"
    ATTENTION = "attention"
    IMPORTANT = "important"
    UNAVAILABLE = "unavailable"


class CheckState(str, Enum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"
    UNAVAILABLE = "unavailable"


@dataclass
class DiagnosticResult:
    title: str
    score: int | None
    coverage: int | None = None
    facts: list[str] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    note: str = ""
    primary_issue: str | None = None
    why_it_matters: str | None = None
    target_doctor: str | None = None
    healthy_areas: int | None = None
    attention_areas: int | None = None
    unavailable_areas: int | None = None
    scan_time: str | None = None
    availability: Availability = Availability.AVAILABLE
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        result = {
            "title": self.title,
            "score": self.score,
            "coverage": self.coverage,
            "facts": list(self.facts),
            "issues": list(self.issues),
            "actions": list(self.actions),
            "note": self.note,
            "primary_issue": self.primary_issue,
            "why_it_matters": self.why_it_matters,
            "target_doctor": self.target_doctor,
            "healthy_areas": self.healthy_areas,
            "attention_areas": self.attention_areas,
            "unavailable_areas": self.unavailable_areas,
            "scan_time": self.scan_time,
            "availability": self.availability.value,
        }
        result.update(self.extra)
        return result
