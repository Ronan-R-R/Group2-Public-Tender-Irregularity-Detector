"""List the suppliers worth looking up on CIPC first.

    uv run python scripts/cipc_worklist.py \\
        --ocds path/to/full.jsonl.gz --out data/cipc/worklist.csv [--top 30]

Only suppliers with an award in the last --recent-months (default 12) are
listed: director data is deleted 12 months after a company's last award (the
privacy notice's retention rule), so looking up an older supplier's directors
would be wasted on the next daily run. They are ranked by the most awards won
from a single buyer, then by total awards. Repeat wins from one buyer are where
the director rules (R4, R6) matter most.

The output only holds eTenders data, but write it under /data/ anyway: the
filled-in CIPC files that follow it hold personal information.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

from detection.rules._dates import months_before
from ingestion.ocds import load_ocds

log = logging.getLogger("cipc_worklist")

COLUMNS = (
    "rank",
    "company_id",
    "etenders_name",
    "awards",
    "most_from_one_buyer",
    "last_award",
    "top_buyers",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--ocds", type=Path, required=True, help="OCDS .jsonl or .jsonl.gz")
    parser.add_argument("--out", type=Path, required=True, help="worklist CSV to write")
    parser.add_argument("--top", type=int, default=30, help="number of suppliers (default 30)")
    parser.add_argument(
        "--recent-months",
        type=int,
        default=12,
        help="only suppliers with an award this recent (default 12, the director retention)",
    )
    parser.add_argument("--today", type=date.fromisoformat, default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.top < 1 or args.recent_months < 1:
        log.error("--top and --recent-months must be at least 1")
        return 2
    if not args.ocds.is_file():
        log.error("OCDS file not found: %s", args.ocds)
        return 2

    loaded, _ = load_ocds(args.ocds)
    today = args.today or date.today()
    cutoff = months_before(today, args.recent_months)
    names: dict[str, str] = {}
    buyers: dict[str, Counter[str]] = defaultdict(Counter)
    latest: dict[str, date] = {}
    for a in loaded:
        names[a.company.company_id] = a.company.name
        buyers[a.company.company_id][a.tender.buyer_name] += 1
        # Same order as purge_expired_directors: award date, else close date.
        day = a.tender.award_date or a.tender.close_date
        if day is not None and day > latest.get(a.company.company_id, date.min):
            latest[a.company.company_id] = day
    recent = [cid for cid in buyers if latest.get(cid, date.min) >= cutoff]

    ranked = sorted(
        recent,
        key=lambda cid: (-max(buyers[cid].values()), -sum(buyers[cid].values()), cid),
    )[: args.top]

    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(COLUMNS)
            for rank, cid in enumerate(ranked, start=1):
                top = "; ".join(f"{b} ({n})" for b, n in buyers[cid].most_common(3))
                writer.writerow(
                    [
                        rank,
                        cid,
                        names[cid],
                        sum(buyers[cid].values()),
                        max(buyers[cid].values()),
                        latest[cid].isoformat(),
                        top,
                    ]
                )
    except OSError as e:
        log.error("could not write %s: %s", args.out, e)
        return 1
    log.info(
        "wrote %d suppliers with an award since %s to %s", len(ranked), cutoff.isoformat(), args.out
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
