"""Write hand-collected CIPC records into the database, and read them back.

The CSV files are the authoritative snapshot for every company they list:
each listed company's CIPC columns, director links and (when looked up)
annual returns are replaced, all in one transaction. Companies the files do
not list are left alone.

Directors linked only to companies that won no award we hold are deleted by
``purge_expired_directors`` on the next scoring run, as the privacy notice
promises.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time

import psycopg

from detection.models import Company, Director
from ingestion.cipc_csv import CipcData, CipcRecord

# Hand-verified against the CIPC register, so the match is certain.
HAND_VERIFIED = 1


@dataclass(frozen=True, slots=True)
class ImportReport:
    companies: int
    directors: int
    links: int
    annual_returns: int


def import_cipc(conn: psycopg.Connection, data: CipcData) -> ImportReport:
    company_ids = list(data.records)
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL search_path = tender")
        cur.executemany(
            "INSERT INTO companies (company_id, name, registration_number, registration_date, "
            "status, industry, cipc_match_confidence, cipc_checked_at, annual_returns_checked) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
            # The eTenders name stays: it is what the dashboard shows.
            "ON CONFLICT (company_id) DO UPDATE SET "
            "registration_number = EXCLUDED.registration_number, "
            "registration_date = EXCLUDED.registration_date, status = EXCLUDED.status, "
            "industry = EXCLUDED.industry, "
            "cipc_match_confidence = EXCLUDED.cipc_match_confidence, "
            "cipc_checked_at = EXCLUDED.cipc_checked_at, "
            # Once looked up, a later file that leaves the column blank does
            # not make the history unknown again; its rows are kept too.
            "annual_returns_checked = "
            "companies.annual_returns_checked OR EXCLUDED.annual_returns_checked",
            [
                (
                    r.company.company_id,
                    r.cipc_name,
                    r.company.registration_number,
                    r.company.registration_date,
                    r.company.status,
                    r.company.industry,
                    HAND_VERIFIED,
                    datetime.combine(r.checked_on, time(12), tzinfo=UTC),
                    r.company.annual_return_dates is not None,
                )
                for r in data.records.values()
            ],
        )

        looked_up = [r for r in data.records.values() if r.company.annual_return_dates is not None]
        cur.execute(
            "DELETE FROM company_annual_returns WHERE company_id = ANY(%s)",
            ([r.company.company_id for r in looked_up],),
        )
        returns = [
            (r.company.company_id, filed)
            for r in looked_up
            for filed in r.company.annual_return_dates or ()
        ]
        cur.executemany(
            "INSERT INTO company_annual_returns (company_id, filed_on) VALUES (%s, %s)", returns
        )

        people = {d.director_id: d for ds in data.directors.values() for d in ds}
        cur.executemany(
            "INSERT INTO directors (director_id, full_name, birth_date) VALUES (%s, %s, %s) "
            "ON CONFLICT (director_id) DO UPDATE SET full_name = EXCLUDED.full_name, "
            "birth_date = EXCLUDED.birth_date",
            [(d.director_id, d.full_name, d.birth_date) for d in people.values()],
        )

        cur.execute("DELETE FROM company_directors WHERE company_id = ANY(%s)", (company_ids,))
        links = [
            (company_id, d.director_id, d.appointed, d.resigned)
            for company_id, ds in data.directors.items()
            for d in ds
        ]
        cur.executemany(
            "INSERT INTO company_directors (company_id, director_id, appointed, resigned) "
            "VALUES (%s, %s, %s, %s)",
            links,
        )

    return ImportReport(
        companies=len(company_ids),
        directors=len(people),
        links=len(links),
        annual_returns=len(returns),
    )


def read_cipc(conn: psycopg.Connection) -> CipcData:
    """Read every CIPC-matched company and its directors back from the database.

    This is what the daily build scores with, so the published results follow
    whatever was last imported. Read in one transaction for a consistent view.
    """
    records: dict[str, CipcRecord] = {}
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL search_path = tender")
        returns: dict[str, list[date]] = defaultdict(list)
        for company_id, filed_on in cur.execute(
            "SELECT company_id, filed_on FROM company_annual_returns ORDER BY company_id, filed_on"
        ):
            returns[company_id].append(filed_on)

        for row in cur.execute(
            "SELECT company_id, name, registration_number, registration_date, status, industry, "
            "annual_returns_checked, cipc_checked_at FROM companies "
            "WHERE registration_number IS NOT NULL AND cipc_checked_at IS NOT NULL"
        ):
            company_id, name, number, registered, status, industry, checked, checked_at = row
            records[company_id] = CipcRecord(
                company=Company(
                    company_id=company_id,
                    name=name,
                    registration_number=number,
                    registration_date=registered,
                    status=status,
                    industry=industry,
                    annual_return_dates=tuple(returns[company_id]) if checked else None,
                ),
                cipc_name=name,
                checked_on=checked_at.date(),
            )

        directors: dict[str, list[Director]] = {company_id: [] for company_id in records}
        for company_id, director_id, full_name, appointed, resigned, born in cur.execute(
            "SELECT cd.company_id, d.director_id, d.full_name, cd.appointed, cd.resigned, "
            "d.birth_date FROM company_directors cd JOIN directors d USING (director_id) "
            "ORDER BY cd.company_id, d.director_id"
        ):
            if company_id in directors:
                directors[company_id].append(
                    Director(director_id, full_name, appointed, resigned, birth_date=born)
                )
    return CipcData(records=records, directors={cid: tuple(ds) for cid, ds in directors.items()})
