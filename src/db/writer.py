"""Write a scoring run to PostgreSQL (Supabase in production).

One call to ``write_run`` is one transaction: the procurement records are
upserted, the run and every rule result are inserted, old runs are pruned and
the director retention purge runs. If anything fails, nothing is written and
the previous run stays the latest.

The connection must be the table owner (the pipeline's own login). Row-level
security is on with no policies, so any other role sees nothing.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb

from detection.export import ScoredAward

SCHEMA_SQL = Path(__file__).with_name("schema.sql")

# Each run is about 115 000 rule results on the full feed. Supabase's free
# tier holds 500 MB, so only the latest few runs are kept.
KEEP_RUNS = 3


@dataclass(frozen=True, slots=True)
class WriteReport:
    run_id: int
    awards: int
    rule_results: int
    runs_pruned: int
    directors_purged: int


def connect(url: str) -> psycopg.Connection:
    # autocommit, so each ``conn.transaction()`` block is a real transaction
    # rather than a savepoint inside one left open by an earlier SELECT.
    # prepare_threshold=None: Supabase's poolers do not support prepared
    # statements in transaction mode, and they buy nothing for one bulk write.
    return psycopg.connect(
        url,
        autocommit=True,
        connect_timeout=30,
        prepare_threshold=None,
        application_name="tender-pipeline",
    )


def ensure_schema(conn: psycopg.Connection) -> bool:
    """Apply schema.sql to an empty database. Returns True if it was applied.

    The schema is created in a single transaction, so one table existing means
    all of them do. Later changes need migrations, not a re-run of this file.
    """
    row = conn.execute("SELECT to_regclass('tender.scoring_runs') IS NOT NULL").fetchone()
    if row is not None and row[0]:
        return False
    with conn.transaction():
        conn.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    return True


def write_run(conn: psycopg.Connection, scored: Sequence[ScoredAward], source: str) -> WriteReport:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute("SET LOCAL search_path = tender")
        _upsert_records(cur, scored)

        cur.execute(
            "INSERT INTO scoring_runs (source, awards_scored) VALUES (%s, %s) RETURNING run_id",
            (source, len(scored)),
        )
        row = cur.fetchone()
        if row is None:
            raise RuntimeError("INSERT ... RETURNING run_id returned no row")
        run_id: int = row[0]

        results = 0
        with cur.copy(
            "COPY risk_scores (run_id, award_id, score, uncapped_score, level, coverage, "
            "needs_review, anomaly_percentile) FROM STDIN"
        ) as copy:
            for s in scored:
                copy.write_row(
                    (
                        run_id,
                        s.tender.tender_id,
                        s.score.score,
                        s.score.uncapped_score,
                        s.score.level.value,
                        round(s.score.coverage, 3),
                        s.score.needs_review,
                        None if s.anomaly is None else round(s.anomaly.percentile, 1),
                    )
                )
        with cur.copy(
            "COPY rule_results (run_id, award_id, rule_id, severity, fired, evaluated, "
            "points, evidence, private_evidence) FROM STDIN"
        ) as copy:
            for s in scored:
                for r in s.score.breakdown:
                    copy.write_row(
                        (
                            run_id,
                            s.tender.tender_id,
                            r.rule_id,
                            r.severity.value,
                            r.fired,
                            r.evaluated,
                            r.score_contribution,
                            Jsonb(r.evidence),
                            Jsonb(r.private_evidence),
                        )
                    )
                    results += 1

        cur.execute(
            "DELETE FROM scoring_runs WHERE run_id NOT IN "
            "(SELECT run_id FROM scoring_runs ORDER BY run_id DESC LIMIT %s)",
            (KEEP_RUNS,),
        )
        pruned = cur.rowcount
        cur.execute("SELECT purge_expired_directors()")
        purged = cur.fetchone()

    return WriteReport(
        run_id=run_id,
        awards=len(scored),
        rule_results=results,
        runs_pruned=pruned,
        directors_purged=0 if purged is None else purged[0],
    )


def _upsert_records(cur: psycopg.Cursor, scored: Sequence[ScoredAward]) -> None:
    buyers: dict[str, str] = {}
    tenders: dict[str, tuple[object, ...]] = {}
    companies: dict[str, str] = {}
    for s in scored:
        t = s.tender
        buyers[t.buyer_id] = t.buyer_name
        # Several awards share one contracting process; the first one describes it.
        tenders.setdefault(
            t.ocid,
            (t.ocid, t.buyer_id, t.title, t.category, t.procurement_method, t.close_date),
        )
        companies[s.company.company_id] = s.company.name

    cur.executemany(
        "INSERT INTO buyers (buyer_id, name) VALUES (%s, %s) "
        "ON CONFLICT (buyer_id) DO UPDATE SET name = EXCLUDED.name",
        list(buyers.items()),
    )
    cur.executemany(
        "INSERT INTO tenders (ocid, buyer_id, title, category, procurement_method, close_date) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (ocid) DO UPDATE SET buyer_id = EXCLUDED.buyer_id, "
        "title = EXCLUDED.title, category = EXCLUDED.category, "
        "procurement_method = EXCLUDED.procurement_method, close_date = EXCLUDED.close_date",
        list(tenders.values()),
    )
    # Only the name comes from eTenders. CIPC columns are filled by enrichment
    # and must survive a daily re-import.
    cur.executemany(
        "INSERT INTO companies (company_id, name) VALUES (%s, %s) "
        "ON CONFLICT (company_id) DO UPDATE SET name = EXCLUDED.name",
        list(companies.items()),
    )
    cur.executemany(
        "INSERT INTO awards (award_id, ocid, supplier_id, value, currency, award_date) "
        "VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (award_id) DO UPDATE SET supplier_id = EXCLUDED.supplier_id, "
        "value = EXCLUDED.value, currency = EXCLUDED.currency, award_date = EXCLUDED.award_date",
        [
            (
                s.tender.tender_id,
                s.tender.ocid,
                s.company.company_id,
                s.tender.award_value,
                s.tender.currency,
                s.tender.award_date,
            )
            for s in scored
        ],
    )
