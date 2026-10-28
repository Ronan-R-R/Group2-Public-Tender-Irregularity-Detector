"""Score an eTenders OCDS export and write the public JSON for the dashboard.

    uv run python scripts/build_dashboard_data.py \\
        --ocds path/to/full.jsonl.gz --out src/frontend/public/data [--write-db]
        [--cipc data/cipc | --cipc-from-db]

With --write-db the run is also written to the database named by the
DATABASE_URL environment variable (never a command-line argument, so it stays
out of process listings and CI logs). With --cipc-from-db the CIPC company and
director records are read from that database, which is how the daily build
picks up whatever was last imported with scripts/import_cipc.py. Reading is
not side-effect free: directors past the 12-month retention are deleted
first, so point DATABASE_URL at production only when you mean to.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import psycopg

from db import writer
from db.cipc_import import read_cipc
from db.writer import describe_db_error
from detection import anomaly, export
from detection.context import InMemoryContext
from detection.engine import evaluate_award
from detection.rules import RULES
from ingestion.cipc_csv import CipcCsvError, CipcData, load_cipc
from ingestion.ocds import load_ocds

OCDS_SOURCE_URL = "https://data.open-contracting.org/en/publication/143"

log = logging.getLogger("build_dashboard_data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--ocds", type=Path, required=True, help="OCDS .jsonl or .jsonl.gz")
    parser.add_argument("--out", type=Path, required=True, help="output directory, replaced")
    parser.add_argument(
        "--write-db", action="store_true", help="also write the run to $DATABASE_URL"
    )
    source = parser.add_mutually_exclusive_group()
    source.add_argument(
        "--cipc",
        type=Path,
        help="directory with companies.csv and directors.csv (see ingestion.cipc_csv)",
    )
    source.add_argument(
        "--cipc-from-db",
        action="store_true",
        help=(
            "read CIPC records from $DATABASE_URL (what the daily build does); "
            "this first deletes directors past retention in that database"
        ),
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.ocds.is_file():
        log.error("OCDS file not found: %s", args.ocds)
        return 2
    database_url = os.environ.get("DATABASE_URL", "")
    if (args.write_db or args.cipc_from_db) and not database_url:
        log.error("--write-db and --cipc-from-db need the DATABASE_URL environment variable")
        return 2

    cipc: CipcData | None = None
    if args.cipc is not None:
        try:
            cipc = load_cipc(args.cipc)
        except CipcCsvError as e:
            log.error("CIPC data rejected, nothing was scored:\n%s", e)
            return 2
    elif args.cipc_from_db:
        try:
            with writer.connect(database_url) as conn:
                if writer.ensure_schema(conn):
                    log.info("database was empty; applied schema.sql")
                for version in writer.migrate(conn):
                    log.info("applied migration %s", version)
                # Directors past retention must not be scored, even once more.
                conn.execute("SELECT tender.purge_expired_directors()")
                cipc = read_cipc(conn)
        except psycopg.Error as e:
            log.error(
                "could not read CIPC data, nothing was scored: %s",
                describe_db_error(e, database_url),
            )
            return 3
    if cipc is not None:
        log.info(
            "CIPC data: %d companies, %d directors",
            len(cipc.records),
            sum(len(d) for d in cipc.directors.values()),
        )

    loaded, report = load_ocds(args.ocds)
    log.info("read %d releases, %d awards", report.records, report.awards)
    for reason, count in report.skipped.most_common():
        log.warning("skipped %d: %s", count, reason)
    if not loaded:
        log.error("no awards loaded; refusing to publish an empty site")
        return 1

    companies = {a.company.company_id: a.company for a in loaded}
    if cipc is not None:
        for company_id, company in companies.items():
            companies[company_id] = cipc.company(company_id, company.name) or company
        unmatched = set(cipc.records) - set(companies)
        if unmatched:
            log.warning("%d CIPC companies won no award in this feed", len(unmatched))
    company_directors = cipc.directors if cipc is not None else {}
    ctx = InMemoryContext(
        (a.tender for a in loaded),
        company_directors=company_directors,
        companies=companies.values(),
    )
    signals = anomaly.score_awards([a.tender for a in loaded])
    log.info("anomaly signal computed for %d priced awards", len(signals))

    scored = [
        export.ScoredAward(
            tender=item.tender,
            company=companies[item.company.company_id],
            score=evaluate_award(
                item.tender,
                companies[item.company.company_id],
                company_directors.get(item.company.company_id, ()),
                ctx,
            ),
            anomaly=signals.get(item.tender.tender_id),
        )
        for item in loaded
    ]

    # Export once, after every award has been scored.
    index, shards = export.build(
        scored,
        RULES,
        generated_at=datetime.now(UTC),
        source={
            "name": "National Treasury eTenders OCDS feed",
            "url": OCDS_SOURCE_URL,
            "licence": "PDDL",
            "releases": report.records,
            "awards": report.awards,
            "skipped": sum(report.skipped.values()),
        },
    )
    export.write(args.out, index, shards)
    log.info("wrote %d awards in %d detail shards to %s", len(scored), len(shards), args.out)

    if args.write_db:
        try:
            with writer.connect(database_url) as conn:
                if writer.ensure_schema(conn):
                    log.info("database was empty; applied schema.sql")
                for version in writer.migrate(conn):
                    log.info("applied migration %s", version)
                result = writer.write_run(conn, scored, OCDS_SOURCE_URL)
        except psycopg.Error as e:
            log.error(
                "database write failed, nothing was committed: %s",
                describe_db_error(e, database_url),
            )
            return 3
        log.info(
            "database run %d: %d awards, %d rule results, %d old runs pruned, "
            "%d directors past retention deleted",
            result.run_id,
            result.awards,
            result.rule_results,
            result.runs_pruned,
            result.directors_purged,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
