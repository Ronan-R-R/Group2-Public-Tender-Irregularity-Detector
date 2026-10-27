"""Score an eTenders OCDS export and write the evaluation report for Chapter 5.

    uv run python scripts/evaluate_detection.py \\
        --ocds path/to/full.jsonl.gz --out evaluation.md

The report is Markdown, ready to paste into the wiki. It scores exactly as the
published build does (no sample registry), so its figures match the site.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from detection import anomaly, export
from detection.context import InMemoryContext
from detection.engine import evaluate_award
from detection.evaluation import CAPTURE_ERROR_RATIO, TOP_ANOMALY_SHARE, Evaluation, evaluate
from ingestion.ocds import LoadReport, load_ocds

log = logging.getLogger("evaluate_detection")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--ocds", type=Path, required=True, help="OCDS .jsonl or .jsonl.gz")
    parser.add_argument("--out", type=Path, required=True, help="Markdown report to write")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if not args.ocds.is_file():
        log.error("OCDS file not found: %s", args.ocds)
        return 2

    started = time.perf_counter()
    loaded, report = load_ocds(args.ocds)
    if not loaded:
        log.error("no awards loaded; nothing to evaluate")
        return 1
    ctx = InMemoryContext(a.tender for a in loaded)
    signals = anomaly.score_awards([a.tender for a in loaded])
    scored = [
        export.ScoredAward(
            a.tender,
            a.company,
            evaluate_award(a.tender, a.company, (), ctx),
            signals.get(a.tender.tender_id),
        )
        for a in loaded
    ]
    elapsed = time.perf_counter() - started

    result = evaluate(scored)
    digest = hashlib.sha256(args.ocds.read_bytes()).hexdigest()[:12]
    try:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(render(result, report, digest, elapsed), encoding="utf-8")
    except OSError as e:
        log.error("could not write %s: %s", args.out, e)
        return 1
    log.info("evaluated %d awards in %.1f s; report at %s", result.awards, elapsed, args.out)
    return 0


def render(result: Evaluation, report: LoadReport, digest: str, elapsed: float) -> str:
    lines = [
        "# Detection evaluation",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC by `scripts/evaluate_detection.py` "
        f"from the eTenders OCDS feed (file sha256 `{digest}...`).",
        "",
        "## Dataset",
        "",
        "| Measure | Value |",
        "|---|---|",
        f"| Releases read | {report.records:,} |",
        f"| Awards loaded | {report.awards:,} |",
        f"| Awards skipped | {sum(report.skipped.values()):,} |",
        f"| Awards scored | {result.awards:,} |",
        f"| Time to load, score and rank all awards | {elapsed:.1f} s |",
        "",
    ]
    if report.skipped:
        lines += ["| Skip reason | Awards |", "|---|---|"]
        lines += [f"| {reason} | {n:,} |" for reason, n in report.skipped.most_common()]
        lines.append("")

    lines += [
        "## Rules",
        "",
        "Fire rate is the share of awards the rule could evaluate on which it fired.",
        "",
        "| Rule | Severity | Evaluated | Fired | Fire rate | Not evaluated |",
        "|---|---|---|---|---|---|",
    ]
    for r in result.rules:
        rate = "n/a" if r.fire_rate is None else f"{r.fire_rate:.1%}"
        lines.append(
            f"| {r.rule_id} {r.title} | {r.severity} | {r.evaluated:,} | {r.fired:,} | "
            f"{rate} | {r.not_evaluated:,} |"
        )

    lines += [
        "",
        "## Why rules could not run",
        "",
        "| Rule | Reason | Awards |",
        "|---|---|---|",
    ]
    for r in result.rules:
        lines += [f"| {r.rule_id} | {reason} | {n:,} |" for reason, n in r.reasons]

    lines += [
        "",
        "## Scores",
        "",
        f"Awards with at least one fired rule: {result.awards_with_a_flag:,} "
        f"({result.awards_with_a_flag / result.awards:.1%}). Highest score: {result.max_score}.",
        "",
        "| Score band | Awards |",
        "|---|---|",
    ]
    lines += [f"| {band} | {n:,} |" for band, n in result.score_bands.items()]
    lines += ["", "| Level | Awards |", "|---|---|"]
    lines += [f"| {level} | {n:,} |" for level, n in result.levels.items()]
    lines += [
        "",
        f"Mean coverage: {result.mean_coverage:.1%} of rules could be evaluated per award.",
        "",
        "| Coverage | Awards |",
        "|---|---|",
    ]
    lines += [f"| {c:.1%} | {n:,} |" for c, n in result.coverage_counts.items()]

    if result.rule_pairs:
        lines += ["", "## Rules firing together", "", "| Pair | Awards |", "|---|---|"]
        lines += [f"| {a} + {b} | {n:,} |" for (a, b), n in list(result.rule_pairs.items())[:10]]

    a = result.anomaly
    lines += ["", "## Isolation Forest", ""]
    if a is None:
        lines.append("Not enough priced awards to train the model; no anomaly signal.")
    else:
        lines += [
            f"Awards with an anomaly percentile: {a.scored:,}. "
            f"Of the top {TOP_ANOMALY_SHARE:.0%} ({a.top_n:,} awards):",
            "",
            f"- {a.top_with_price_flag:,} ({a.top_with_price_flag / a.top_n:.0%}) also fire "
            "R10 or R11;",
            f"- {a.top_capture_errors:,} ({a.top_capture_errors / a.top_n:.0%}) are at least "
            f"{CAPTURE_ERROR_RATIO:.0f} times off their category's typical value, which "
            "points to capture errors rather than mispricing.",
        ]
    lines += [
        "",
        "## Limits",
        "",
        "- There is no labelled ground truth for irregular South African tenders, so these "
        "figures describe how the rules behave, not how accurate they are.",
        "- No CIPC company or director data is loaded, so R1-R6 and R9 are not evaluated "
        "on any award. The rules that can run (R7, R8, R10 or R11, R12) add up to at most "
        "34 points, below the flag line of 50, so no award can be flagged yet.",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
