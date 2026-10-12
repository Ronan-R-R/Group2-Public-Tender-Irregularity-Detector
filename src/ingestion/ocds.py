"""Load eTenders awards from an OCDS JSON Lines export.

Source: National Treasury eTenders OCDS feed as mirrored by the Open
Contracting data registry (publication 143, PDDL), one compiled release per
line, optionally gzip-compressed.

This is the minimal reader the scoring job needs. Writing to Postgres is
issue #8 and builds on it.

Mapping decisions, each driven by what the feed actually contains:

- One ``Tender`` per award, ``tender_id = "<ocid>/<award id>"``.
- Supplier id "0" is shared by 37% of awards across unrelated companies, so
  those suppliers are keyed by normalised name instead (``name:...``).
- Award value 0 means "not captured" (2,791 awards) and becomes None.
- Dates before 2000 are .NET's 0001-01-01 default and become None.
- ``tender.tenderers`` is not treated as a bid list: in 1,090 of 1,361
  awarded processes it does not contain the winning supplier. It is mapped to
  None (unpublished), so R8 relies on the procurement method.
- Procurement officials' names, emails and phone numbers are never read.
"""

from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from detection.models import EARLIEST_PLAUSIBLE_DATE, PLACEHOLDER_IDS, Company, Tender

_CSD_PREFIX = re.compile(r"^\s*MAAA\d+\s*-\s*", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^A-Z0-9]+")
_MAX_NAME = 300


@dataclass(frozen=True, slots=True)
class LoadedAward:
    tender: Tender
    company: Company


@dataclass
class LoadReport:
    records: int = 0
    awards: int = 0
    skipped: Counter[str] = field(default_factory=Counter)


def display_name(raw: str) -> str:
    """Readable supplier name: CSD prefix and wrapping brackets removed."""
    name = _CSD_PREFIX.sub("", raw[:_MAX_NAME]).strip()
    while name.startswith("(") and name.endswith(")"):
        name = name[1:-1].strip()
    if name.startswith("(") and name.count("(") > name.count(")"):
        name = name[1:].strip()
    return " ".join(name.split())


def name_key(raw: str) -> str:
    return _NON_ALNUM.sub(" ", display_name(raw).upper()).strip()


def _date(value: object) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        parsed = date.fromisoformat(value[:10])
    except ValueError:
        return None
    return parsed if parsed >= EARLIEST_PLAUSIBLE_DATE else None


def _amount(value: object) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value))
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount <= 0:
        return None
    return amount


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    cleaned = " ".join(value.split())
    return cleaned[:_MAX_NAME] or None


def _supplier(raw: Mapping[str, Any]) -> tuple[str, str] | None:
    name = display_name(str(raw.get("name") or ""))
    supplier_id = str(raw.get("id") or "").strip()
    if supplier_id and supplier_id not in PLACEHOLDER_IDS:
        return f"etenders:{supplier_id}", name or supplier_id
    key = name_key(name)
    if not key:
        return None
    return f"name:{key}", name


def awards_from_release(release: Mapping[str, Any], report: LoadReport) -> Iterator[LoadedAward]:
    awards = release.get("awards") or []
    if not awards:
        return
    ocid = str(release.get("ocid") or "").strip()
    buyer = release.get("buyer") or {}
    buyer_id = str(buyer.get("id") or "").strip()
    if not ocid or not buyer_id or buyer_id in PLACEHOLDER_IDS:
        report.skipped["missing ocid or buyer"] += len(awards)
        return
    tender = release.get("tender") or {}
    period = tender.get("tenderPeriod") or {}
    category = _text(tender.get("category")) or _text(tender.get("mainProcurementCategory"))

    for award in awards:
        suppliers = award.get("suppliers") or []
        resolved = _supplier(suppliers[0]) if suppliers else None
        if resolved is None:
            report.skipped["no identifiable supplier"] += 1
            continue
        supplier_key, supplier_name = resolved
        value = award.get("value") or {}
        try:
            scored = Tender(
                tender_id=f"{ocid}/{award.get('id') or len(awards)}",
                ocid=ocid,
                title=_text(tender.get("title")) or "",
                buyer_id=f"etenders:{buyer_id}",
                buyer_name=_text(buyer.get("name")) or buyer_id,
                supplier_id=supplier_key,
                category=category,
                procurement_method=_text(tender.get("procurementMethodDetails")),
                close_date=_date(period.get("endDate")),
                award_value=_amount(value.get("amount")),
                currency=str(value.get("currency") or "ZAR"),
                tenderer_ids=None,
            )
        except ValueError as exc:
            report.skipped[f"invalid award: {exc}"[:80]] += 1
            continue
        report.awards += 1
        yield LoadedAward(scored, Company(company_id=supplier_key, name=supplier_name))


def load_ocds(path: Path) -> tuple[list[LoadedAward], LoadReport]:
    report = LoadReport()
    loaded: list[LoadedAward] = []
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            report.records += 1
            try:
                release = json.loads(line)
            except json.JSONDecodeError:
                report.skipped["unparseable line"] += 1
                continue
            if not isinstance(release, dict):
                report.skipped["line is not a JSON object"] += 1
                continue
            loaded.extend(awards_from_release(release, report))
    return loaded, report
