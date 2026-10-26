"""Score an eTenders OCDS export and write the public JSON for the dashboard.

    uv run python scripts/build_dashboard_data.py \\
        --ocds path/to/full.jsonl.gz --out src/frontend/public/data
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from detection import anomaly, export
from detection.context import InMemoryContext
from detection.engine import evaluate_award
from detection.rules import RULES
from ingestion.ocds import load_ocds
from ingestion.sample_registry import sample_company_registry
from ingestion.supplier_company_matcher import match_supplier_to_company

from detection.models import JSONValue

OCDS_SOURCE_URL = "https://data.open-contracting.org/en/publication/143"

log = logging.getLogger("build_dashboard_data")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--ocds", type=Path, required=True, help="OCDS .jsonl or .jsonl.gz")
    parser.add_argument("--out", type=Path, required=True, help="output directory, replaced")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.ocds.is_file():
        log.error("OCDS file not found: %s", args.ocds)
        return 2

    loaded, report = load_ocds(args.ocds)
    log.info("read %d releases, %d awards", report.records, report.awards)
    for reason, count in report.skipped.most_common():
        log.warning("skipped %d: %s", count, reason)
    if not loaded:
        log.error("no awards loaded; refusing to publish an empty site")
        return 1

    ctx = InMemoryContext(a.tender for a in loaded)
    signals = anomaly.score_awards([a.tender for a in loaded])
    log.info("anomaly signal computed for %d priced awards", len(signals))

    """ scored = [
        export.ScoredAward(
            a.tender,
            a.company,
            evaluate_award(a.tender, a.company, (), ctx),
            signals.get(a.tender.tender_id),
        )
        for a in loaded
    ] """
    # Load the small demo registry. This is sample data, not a complete CIPC dataset.
    # Demo registry only; these are not live or complete CIPC records.
    sample_companies = sample_company_registry()
    sample_names = [record.legal_name for record in sample_companies]

    scored = []
    for item in loaded:
        match = match_supplier_to_company(
            item.company.name,
            sample_names,
            source="sample",
        )

        # This is a name-similarity score, not a probability of identity.
        match_metadata: dict[str, JSONValue] = {
            "status": match.status,
            "confidence": round(match.confidence, 3),
            "matched_company_name": match.matched_company_name,
            "source": match.source,
        }

        scored.append(
            export.ScoredAward(
                tender=item.tender,
                company=item.company,
                score=evaluate_award(item.tender, item.company, (), ctx),
                anomaly=signals.get(item.tender.tender_id),
                supplier_match=match_metadata,
            )
        )

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
    return 0




if __name__ == "__main__":
    sys.exit(main())
