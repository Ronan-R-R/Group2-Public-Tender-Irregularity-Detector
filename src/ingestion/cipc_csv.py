"""Load CIPC company and director records from two CSV files.

The files are filled in by hand from the CIPC company search (see the wiki
page CIPC-Data-Access) and later, possibly, by a paid registry API. Both
produce the same two files, so the rules never know which source was used.

companies.csv::

    company_id,cipc_name,registration_number,registration_date,status,industry,
    annual_return_dates,checked_on

directors.csv::

    company_id,director_id,full_name,appointed,resigned

- ``company_id`` is the supplier key from the eTenders loader, ``etenders:<id>``
  or ``name:<KEY>``, so each row finds its awards.
- ``annual_return_dates`` is ``;``-separated ISO dates. Blank means the filing
  history was not looked up (R3 is not evaluated); ``none`` means it was looked
  up and nothing was ever filed.
- ``director_id`` is an invented pseudonymous key such as ``dir-0001``. It is
  the only director field that may reach the public site. ``full_name`` is
  personal information under POPIA: the real files stay out of the repository.

Every problem in a file is collected and reported together with its line
number. Nothing is skipped silently: a half-loaded registry would make rules
report "clear" for suppliers whose data was simply dropped.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from detection.models import Company, Director

COMPANY_COLUMNS = (
    "company_id",
    "cipc_name",
    "registration_number",
    "registration_date",
    "status",
    "industry",
    "annual_return_dates",
    "checked_on",
)
DIRECTOR_COLUMNS = ("company_id", "director_id", "full_name", "appointed", "resigned")

# CIPC numbers look like 2019/123456/07: year, sequence, entity type.
_REGISTRATION_NUMBER = re.compile(r"^\d{4}/\d{6}/\d{2}$")
_COMPANY_ID = re.compile(r"^(etenders:[0-9A-Za-z-]{1,40}|name:[A-Z0-9 ]{1,200})$")
_DIRECTOR_ID = re.compile(r"^[a-z0-9-]{3,40}$")
# A 13-digit value is a South African ID number. It must never be used as the
# public director key.
_SA_ID_NUMBER = re.compile(r"^\d{13}$")
_MAX_TEXT = 300
# Companies registered long before eTenders existed still win tenders, so the
# floor is far earlier than the procurement-date floor in detection.models.
_EARLIEST_REGISTRY_DATE = date(1900, 1, 1)
_MAX_ERRORS_SHOWN = 50


class CipcCsvError(ValueError):
    def __init__(self, path: Path, errors: list[str]) -> None:
        shown = errors[:_MAX_ERRORS_SHOWN]
        more = len(errors) - len(shown)
        lines = "\n".join(f"  {e}" for e in shown)
        suffix = f"\n  ... and {more} more" if more else ""
        super().__init__(f"{path.name}: {len(errors)} problem(s)\n{lines}{suffix}")
        self.errors = errors


@dataclass(frozen=True, slots=True)
class CipcRecord:
    company: Company
    cipc_name: str
    checked_on: date


@dataclass(frozen=True, slots=True)
class CipcData:
    records: Mapping[str, CipcRecord]
    directors: Mapping[str, tuple[Director, ...]]

    def company(self, company_id: str, etenders_name: str) -> Company | None:
        """The CIPC-enriched company for a supplier, keeping the eTenders name."""
        record = self.records.get(company_id)
        if record is None:
            return None
        c = record.company
        return Company(
            company_id=c.company_id,
            name=etenders_name,
            registration_number=c.registration_number,
            registration_date=c.registration_date,
            status=c.status,
            industry=c.industry,
            annual_return_dates=c.annual_return_dates,
        )


def load_cipc(directory: Path) -> CipcData:
    """Load ``companies.csv`` and ``directors.csv`` from ``directory``."""
    records = _load_companies(directory / "companies.csv")
    directors = _load_directors(directory / "directors.csv", records)
    return CipcData(records=records, directors=directors)


def _rows(path: Path, columns: tuple[str, ...]) -> Iterator[tuple[int, dict[str, str]]]:
    try:
        handle = path.open(encoding="utf-8-sig", newline="")
    except OSError as e:
        raise CipcCsvError(path, [f"cannot open: {e.strerror}"]) from e
    with handle:
        reader = csv.DictReader(handle)
        header = tuple(reader.fieldnames or ())
        if header != columns:
            raise CipcCsvError(
                path, [f"header must be exactly: {','.join(columns)} (got {','.join(header)})"]
            )
        for row in reader:
            if None in row:
                yield reader.line_num, {"__extra__": "x"}
                continue
            yield reader.line_num, {k: (v or "").strip() for k, v in row.items()}


def _date(value: str, field: str, errors: list[str], line: int) -> date | None:
    if not value:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        errors.append(f"line {line}: {field} {value!r} is not a YYYY-MM-DD date")
        return None
    if parsed < _EARLIEST_REGISTRY_DATE or parsed > date.today():
        errors.append(f"line {line}: {field} {value} is not a plausible date")
        return None
    return parsed


def _text(value: str, field: str, errors: list[str], line: int, required: bool) -> str | None:
    if not value:
        if required:
            errors.append(f"line {line}: {field} is required")
        return None
    if len(value) > _MAX_TEXT:
        errors.append(f"line {line}: {field} is longer than {_MAX_TEXT} characters")
        return None
    return value


def _load_companies(path: Path) -> dict[str, CipcRecord]:
    errors: list[str] = []
    records: dict[str, CipcRecord] = {}
    registration_numbers: dict[str, int] = {}
    for line, row in _rows(path, COMPANY_COLUMNS):
        if "__extra__" in row:
            errors.append(f"line {line}: more values than columns")
            continue
        company_id = row["company_id"]
        if not _COMPANY_ID.match(company_id):
            errors.append(f"line {line}: company_id {company_id!r} is not an eTenders supplier key")
            continue
        if company_id in records:
            errors.append(f"line {line}: company_id {company_id} appears twice")
            continue

        number = row["registration_number"]
        if not _REGISTRATION_NUMBER.match(number):
            errors.append(f"line {line}: registration_number {number!r} is not like 2019/123456/07")
        elif number in registration_numbers:
            errors.append(
                f"line {line}: registration_number {number} is also on line "
                f"{registration_numbers[number]}"
            )
        else:
            registration_numbers[number] = line

        cipc_name = _text(row["cipc_name"], "cipc_name", errors, line, required=True)
        registered = _date(row["registration_date"], "registration_date", errors, line)
        checked_on = _date(row["checked_on"], "checked_on", errors, line)
        if checked_on is None and not row["checked_on"]:
            errors.append(f"line {line}: checked_on is required")
        status = _text(row["status"], "status", errors, line, required=False)
        industry = _text(row["industry"], "industry", errors, line, required=False)
        returns = _annual_returns(row["annual_return_dates"], errors, line)
        if registered and returns and min(returns) < registered:
            errors.append(f"line {line}: an annual return predates registration")

        if cipc_name is None or checked_on is None or not _REGISTRATION_NUMBER.match(number):
            continue
        records[company_id] = CipcRecord(
            company=Company(
                company_id=company_id,
                name=cipc_name,
                registration_number=number,
                registration_date=registered,
                status=status,
                industry=industry,
                annual_return_dates=returns,
            ),
            cipc_name=cipc_name,
            checked_on=checked_on,
        )
    if errors:
        raise CipcCsvError(path, errors)
    return records


def _annual_returns(value: str, errors: list[str], line: int) -> tuple[date, ...] | None:
    if not value:
        return None
    if value.lower() == "none":
        return ()
    dates: list[date] = []
    for part in value.split(";"):
        parsed = _date(part.strip(), "annual_return_dates", errors, line)
        if parsed is not None:
            dates.append(parsed)
    return tuple(sorted(set(dates)))


def _load_directors(
    path: Path, records: Mapping[str, CipcRecord]
) -> dict[str, tuple[Director, ...]]:
    errors: list[str] = []
    by_company: dict[str, list[Director]] = {company_id: [] for company_id in records}
    seen: dict[tuple[str, str], int] = {}
    names: dict[str, tuple[str, int]] = {}
    for line, row in _rows(path, DIRECTOR_COLUMNS):
        if "__extra__" in row:
            errors.append(f"line {line}: more values than columns")
            continue
        company_id, director_id = row["company_id"], row["director_id"]
        if company_id not in records:
            errors.append(f"line {line}: company_id {company_id!r} is not in companies.csv")
            continue
        if _SA_ID_NUMBER.match(director_id):
            errors.append(
                f"line {line}: director_id looks like an ID number; "
                "use an invented key like dir-0001"
            )
            continue
        if not _DIRECTOR_ID.match(director_id):
            errors.append(f"line {line}: director_id {director_id!r} must be like dir-0001")
            continue
        if (company_id, director_id) in seen:
            errors.append(
                f"line {line}: director {director_id} is already listed for {company_id} "
                f"on line {seen[(company_id, director_id)]}"
            )
            continue
        seen[(company_id, director_id)] = line

        full_name = _text(row["full_name"], "full_name", errors, line, required=True)
        if full_name is None:
            continue
        # The same director_id must mean the same person everywhere, or R4
        # would join two people into one network.
        earlier = names.get(director_id)
        if earlier and earlier[0] != full_name:
            errors.append(
                f"line {line}: director {director_id} has a different name on line {earlier[1]}"
            )
            continue
        names.setdefault(director_id, (full_name, line))

        appointed = _date(row["appointed"], "appointed", errors, line)
        resigned = _date(row["resigned"], "resigned", errors, line)
        if appointed and resigned and resigned < appointed:
            errors.append(f"line {line}: resigned is before appointed")
            continue
        by_company[company_id].append(Director(director_id, full_name, appointed, resigned))
    if errors:
        raise CipcCsvError(path, errors)
    return {company_id: tuple(ds) for company_id, ds in by_company.items()}
