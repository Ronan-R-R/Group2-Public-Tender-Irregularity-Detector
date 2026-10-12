"""Red-flag rule registry. Each rule lives in its own module."""

from __future__ import annotations

from types import ModuleType

from detection.rules import (
    r01_new_company,
    r02_very_new_company,
    r03_dormant_company,
    r07_repeat_winner,
    r08_non_competitive,
    r09_sector_mismatch,
    r10_price_high,
    r11_price_low,
    r12_round_value,
)
from detection.rules._base import Evaluate, Rule


def _from_module(module: ModuleType) -> Rule:
    return Rule(
        rule_id=module.RULE_ID,
        title=module.TITLE,
        severity=module.SEVERITY,
        evaluate=module.evaluate,
    )


RULES: tuple[Rule, ...] = tuple(
    _from_module(m)
    for m in (
        r01_new_company,
        r02_very_new_company,
        r03_dormant_company,
        r07_repeat_winner,
        r08_non_competitive,
        r09_sector_mismatch,
        r10_price_high,
        r11_price_low,
        r12_round_value,
    )
)

__all__ = ["RULES", "Evaluate", "Rule"]
