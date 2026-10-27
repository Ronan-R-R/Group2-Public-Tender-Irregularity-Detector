# Public Tender Irregularity Detector

> **CTU SE2 Capstone Project - Group 2, Boksburg Campus (2026)**
> A civic-technology platform that cross-references South African public tender awards with company and director registries to flag patterns consistent with procurement irregularity.

- **Plan and live status:** [project board](https://github.com/users/Ronan-R-R/projects/8), [project plan](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Project-Plan)
- **Design and requirements:** [wiki](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki): [rule catalogue](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Rule-Catalogue), [architecture decisions](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Architecture-Decisions), [documents index](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Documents)

---

## About This Project

South Africa loses tens of billions of rands annually through irregular, wasteful, and corrupt public procurement. The National Treasury publishes every awarded tender on the [eTenders portal](https://www.etenders.gov.za/), and the Companies and Intellectual Property Commission (CIPC) maintains a public register of companies and directors. No publicly available tool currently joins these datasets and applies automated red-flag detection to the result.

This project closes that gap. It ingests tender award data continuously, enriches each award with director and company information from CIPC, applies a rules engine built on the Transparency International, World Bank and Fazekas et al. red-flag frameworks plus an Isolation Forest pricing signal, and surfaces a per-award risk score with full rule-level transparency. Scores are indicators for human review, not findings of wrongdoing.

### Website

- **Tender Risk Monitor:** [g2-tender-monitor.pages.dev](https://g2-tender-monitor.pages.dev). It covers four screens:
  - an overview of every scored eTenders award;
  - a filterable tender list;
  - a per-tender page with the rule-by-rule breakdown and price comparison;
  - a page per buyer.

  Production redeploys from the latest data on every merge to `main`. Every pull request gets its own preview deployment; the link is posted as a comment on the PR.

Run it locally with real data (needs Node 24 and the [eTenders OCDS file](https://data.open-contracting.org/en/publication/143/download?name=full.jsonl.gz), 12 MB):

```bash
uv run python scripts/build_dashboard_data.py --ocds path/to/full.jsonl.gz --out src/frontend/public/data
cd src/frontend
npm ci
npm run dev
```

## Target Users

- Auditor-General of South Africa (AGSA)
- Standing Committee on Public Accounts (SCOPA)
- Civil-society watchdogs: OUTA, Corruption Watch
- Investigative journalists: amaBhungane, Daily Maverick
- Members of the public and taxpayers

## Technology Stack

- Python 3.11+, managed with [uv](https://docs.astral.sh/uv/)
- PostgreSQL 17 (Supabase free tier in production, Docker locally)
- scikit-learn Isolation Forest for pricing anomalies
- FastAPI for local development and the live demo only, not deployed
- React + Vite + Tailwind CSS dashboard on Cloudflare Pages
- GitHub Actions cron runs scraping and scoring; the dashboard reads the JSON it publishes
- ruff, mypy (strict) and pytest for code quality

Nothing runs as a hosted server. The scheduled workflow scrapes, scores, writes to Supabase and publishes static JSON for the dashboard. Reasons for each choice are in [architecture decisions](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Architecture-Decisions).

## Repository Structure

```
docs/            Dissertation chapters and assessment artefacts (design docs live in the GitHub Wiki)
src/
  ingestion/     Tender and company data collection
  detection/     Red-flag rules, composite risk score, Isolation Forest
  db/            PostgreSQL schema
  api/           FastAPI app for local use and the demo
  frontend/      Dashboard (React, Vite, Tailwind), reads the exported JSON
tests/           Test suites
scripts/         One-off and operational scripts
```

## Getting Started

Prerequisites: [uv](https://docs.astral.sh/uv/getting-started/installation/), and Docker if you want a local database.

```bash
uv sync
uv run pytest
```

`uv sync` installs Python 3.11 if needed and creates `.venv` from `uv.lock`.

Local database:

```bash
cp .env.example .env    # then set POSTGRES_PASSWORD and DATABASE_URL
docker compose up -d
```

`src/db/schema.sql` is applied only when the `pgdata` volume is first created. After a schema change, reset with `docker compose down -v && docker compose up -d`. This deletes all local data.

The schema tests need a database whose name ends in `_test`, because they drop and recreate the `tender` schema. CI runs them against Postgres 17.6 on every PR. To run them locally against the compose database:

```bash
docker compose exec db createdb -U tender tender_test
TEST_DATABASE_URL=postgresql://tender:<password>@localhost:5432/tender_test uv run pytest tests/db
```

Checks to run before pushing:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

## Contributing

1. Pick an issue from the [project board](https://github.com/users/Ronan-R-R/projects/8) and branch from `main`: `feat/...`, `fix/...` or `docs/...`.
2. Commit under your own GitHub account. The assessment rubric marks team development evidence and individual contribution.
3. Open a pull request into `main` with `Closes #N` in the description. `main` only accepts changes through pull requests.
4. After merging, delete the branch.

Design documents (SRS, architecture, UML, database design, test plan) go in the [wiki](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Documents), not in `docs/`.

## Project Team

| Member | Role | Responsibility |
|---|---|---|
| Eugene | Group Lead | Chapters 1 & 6; consolidation; client liaison |
| Michael | Member | Chapters 3 & 4; architecture; repository ownership |
| Sebastian | Member | Chapter 5; data pipeline; testing |
| Ronan | Member | Chapter 2; detection engine; scoring logic |
| Nhlanhla | Presenter | Dashboard; final presentation and demonstration |

## Academic Context

- **Institution:** [CTU Training Solutions](https://www.ctutraining.ac.za/), Boksburg Campus
- **Module:** Software Engineering 2 (SE2) - Capstone
- **Supervisor:** Ms Amenda
- **Academic Year:** 2026
- **Methodology:** Agile Scrum, one-week sprints (12-18 Oct, 19-25 Oct, release 26-29 Oct)

## Key Data Sources

- [National Treasury eTenders Portal](https://www.etenders.gov.za/)
- [eTenders OCDS bulk data](https://data.open-contracting.org/en/publication/143) (Open Contracting data registry, PDDL), the primary source for award history
- [Companies and Intellectual Property Commission (CIPC)](https://www.cipc.co.za/)
- [Open Contracting Data Standard (OCDS)](https://www.open-contracting.org/data-standard/)

## Methodological Foundations

- Fazekas, Toth and King (2016) - Corruption Risk Index
- Transparency International (2014) - Procurement red-flag framework
- World Bank Group (2013) - Fraud and corruption awareness handbook
- Liu, Ting and Zhou (2008) - Isolation Forest algorithm

Full reference list in `docs/02_Literature_Review/`.


## CIPC Enrichment Update

This branch introduces the initial CIPC enrichment layer for the highest-risk supplier matching flow. The system now supports:

- supplier-to-company matching using name-based enrichment and normalisation
- director linkage by comparing supplier names against CIPC company/director records
- a confidence score to distinguish strong matches from weak or ambiguous matches
- a fallback strategy that documents manual verification when official enrichment is unavailable

### In progress / required updates

The current implementation is a working baseline and still needs refinement before it can be treated as a definitive registry match:

- tighten name standardisation for trading names, legal names, abbreviations, and duplicate variants
- improve the matching logic for low-confidence or partial director matches
- document and enforce the official data route decision (CIPC, OpenCorporates, or verified sample)
- add clearer handling for unresolved or ambiguous companies so they are not treated as confirmed matches
- extend the evidence trail so each linkage can be explained and reviewed



## Licence

This project is released under the [MIT Licence](LICENSE) for academic and research reuse.

## Status

Active development. Code freeze **Tuesday 27 October 2026, 18:00**; final capstone submission **Thursday 29 October 2026**.

Detection engine: all twelve rules, the composite score and the Isolation Forest signal are implemented, and the PostgreSQL schema is in `src/db/schema.sql`. On the eTenders feed, R7, R8, R10, R11, R12 and the Isolation Forest produce results today. R1-R6 and R9 report "not evaluated" until CIPC company and director data is loaded ([#24](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/issues/24)). Per-rule status is in the [rule catalogue](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Rule-Catalogue).
