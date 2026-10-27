"""Write hand-collected CIPC records into the database.

The CSV files are the authoritative snapshot for every company they list:
each listed company's CIPC columns, director links and (when looked up)
annual returns are replaced, all in one transaction. Companies the files do
not list are left alone.

Directors linked only to companies that won no award we hold are deleted by
``purge_expired_directors`` on the next scoring run, as the privacy notice
promises.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, time

import psycopg

from ingestion.cipc_csv import CipcData

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
            "status, industry, cipc_match_confidence, cipc_checked_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
            # The eTenders name stays: it is what the dashboard shows.
            "ON CONFLICT (company_id) DO UPDATE SET "
            "registration_number = EXCLUDED.registration_number, "
            "registration_date = EXCLUDED.registration_date, status = EXCLUDED.status, "
            "industry = EXCLUDED.industry, "
            "cipc_match_confidence = EXCLUDED.cipc_match_confidence, "
            "cipc_checked_at = EXCLUDED.cipc_checked_at",
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
