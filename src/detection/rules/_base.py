from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from detection.context import DetectionContext
from detection.models import Company, Director, RuleResult, Severity, Tender

Evaluate = Callable[[Tender, Company, Sequence[Director], DetectionContext], RuleResult]


@dataclass(frozen=True, slots=True)
class Rule:
    rule_id: str
    title: str
    severity: Severity
    evaluate: Evaluate
