"""Public JSON export: the contract between the scoring job and any frontend.

Layout under the output directory:

- ``index.json``: rule catalogue, thresholds, summary counts and one compact
  row per award, ranked by score. Enough to render the ranked list.
- ``details/<shard>.json``: the full rule-by-rule breakdown for each award,
  keyed by ``tender_id``. ``shard`` is the first two hex characters of the
  SHA-256 of ``tender_id`` and is also given on each index row, so a client
  fetches one small file per detail view instead of every breakdown.

Never exported: ``private_evidence`` (director names, PEP matches) and
anything about natural persons. Comparable-award lists are kept only on
rules that fired, which is where a price chart is shown; that keeps the
details files small.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from detection.models import Company, JSONValue, RuleResult, Tender
from detection.rules import Rule
from detection.scorer import (
    ALERT_THRESHOLD,
    FLAG_THRESHOLD,
    MAX_SCORE,
    CompositeRiskScore,
    RiskLevel,
)

SCHEMA_VERSION = 1
_LEVEL_ORDER = {RiskLevel.ALERT: 0, RiskLevel.FLAG: 1, RiskLevel.NONE: 2}
_FIRED_ONLY_KEYS = frozenset({"comparables"})


@dataclass(frozen=True, slots=True)
class ScoredAward:
    tender: Tender
    company: Company
    score: CompositeRiskScore


def shard_of(tender_id: str) -> str:
    return hashlib.sha256(tender_id.encode("utf-8")).hexdigest()[:2]


def public_result(result: RuleResult) -> dict[str, JSONValue]:
    evidence: dict[str, JSONValue] = {
        k: v for k, v in result.evidence.items() if result.fired or k not in _FIRED_ONLY_KEYS
    }
    return {
        "rule_id": result.rule_id,
        "title": result.title,
        "severity": result.severity.value,
        "fired": result.fired,
        "evaluated": result.evaluated,
        "points": result.score_contribution,
        "needs_review": result.needs_review,
        "evidence": evidence,
    }


def index_row(award: ScoredAward) -> dict[str, JSONValue]:
    t, s = award.tender, award.score
    fired: list[JSONValue] = [r.rule_id for r in s.fired]
    return {
        "id": t.tender_id,
        "ocid": t.ocid,
        "title": t.title,
        "buyer_id": t.buyer_id,
        "buyer": t.buyer_name,
        "supplier_id": t.supplier_id,
        "supplier": award.company.name,
        "category": t.category,
        "close_date": t.close_date.isoformat() if t.close_date else None,
        "value": str(t.award_value) if t.award_value is not None else None,
        "score": s.score,
        "level": s.level.value,
        "fired": fired,
        "coverage": round(s.coverage, 3),
        "needs_review": s.needs_review,
        "shard": shard_of(t.tender_id),
    }


def detail_record(award: ScoredAward) -> dict[str, JSONValue]:
    breakdown: list[JSONValue] = [public_result(r) for r in award.score.breakdown]
    return {
        "id": award.tender.tender_id,
        "score": award.score.score,
        "uncapped_score": award.score.uncapped_score,
        "level": award.score.level.value,
        "coverage": round(award.score.coverage, 3),
        "breakdown": breakdown,
    }


def build(
    awards: Sequence[ScoredAward],
    rules: Iterable[Rule],
    generated_at: datetime,
    source: Mapping[str, JSONValue],
) -> tuple[dict[str, JSONValue], dict[str, dict[str, JSONValue]]]:
    if generated_at.tzinfo is None:
        raise ValueError("generated_at must be timezone-aware")
    ids = [a.tender.tender_id for a in awards]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate tender_id in export")

    ranked = sorted(
        awards,
        key=lambda a: (
            _LEVEL_ORDER[a.score.level],
            -a.score.score,
            -(a.tender.award_value or 0),
            a.tender.tender_id,
        ),
    )
    fired: Counter[str] = Counter()
    unevaluated: Counter[str] = Counter()
    levels: Counter[str] = Counter()
    shards: dict[str, dict[str, JSONValue]] = {}
    for award in ranked:
        levels[award.score.level.value] += 1
        for r in award.score.breakdown:
            fired[r.rule_id] += r.fired
            unevaluated[r.rule_id] += not r.evaluated
        shards.setdefault(shard_of(award.tender.tender_id), {})[award.tender.tender_id] = (
            detail_record(award)
        )

    catalogue: list[JSONValue] = [
        {
            "id": r.rule_id,
            "title": r.title,
            "severity": r.severity.value,
            "points": r.severity.weight,
        }
        for r in rules
    ]
    rows: list[JSONValue] = [index_row(a) for a in ranked]
    index: dict[str, JSONValue] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at.isoformat(),
        "source": dict(source),
        "thresholds": {"flag": FLAG_THRESHOLD, "alert": ALERT_THRESHOLD, "max": MAX_SCORE},
        "rules": catalogue,
        "summary": {
            "awards": len(ranked),
            "by_level": dict(levels),
            "fired": dict(fired),
            "not_evaluated": dict(unevaluated),
        },
        "awards": rows,
    }
    return index, shards


def write(
    out_dir: Path, index: dict[str, JSONValue], shards: dict[str, dict[str, JSONValue]]
) -> None:
    """Replace ``out_dir`` with a fresh export."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    details = out_dir / "details"
    details.mkdir(parents=True)
    _dump(out_dir / "index.json", index)
    for shard, records in shards.items():
        _dump(details / f"{shard}.json", records)


def _dump(path: Path, payload: object) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
