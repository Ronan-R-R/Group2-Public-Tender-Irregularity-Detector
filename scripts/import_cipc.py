"""Import hand-collected CIPC records into the database.

    DATABASE_URL=... uv run python scripts/import_cipc.py --cipc data/cipc

Run from your own machine: the real files hold director names and never
leave it. The database is brought up to date (schema or pending migrations)
first. The files are validated in full before anything is written, and the
write is one transaction, so a failure leaves the database as it was.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import psycopg

from db import writer
from db.cipc_import import import_cipc
from db.writer import describe_db_error
from ingestion.cipc_csv import CipcCsvError, load_cipc

log = logging.getLogger("import_cipc")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--cipc", type=Path, required=True, help="directory with companies.csv and directors.csv"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        log.error("set the DATABASE_URL environment variable (the Supabase session pooler URI)")
        return 2
    try:
        data = load_cipc(args.cipc)
    except CipcCsvError as e:
        log.error("CIPC data rejected, nothing was imported:\n%s", e)
        return 2

    try:
        with writer.connect(database_url) as conn:
            if writer.ensure_schema(conn):
                log.info("database was empty; applied schema.sql")
            for version in writer.migrate(conn):
                log.info("applied migration %s", version)
            report = import_cipc(conn, data)
    except psycopg.Error as e:
        log.error("import failed, nothing was committed: %s", describe_db_error(e, database_url))
        return 3
    log.info(
        "imported %d companies, %d directors, %d director links, %d annual returns",
        report.companies,
        report.directors,
        report.links,
        report.annual_returns,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
