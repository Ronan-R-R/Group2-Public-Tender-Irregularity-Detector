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

- **Detection review:** [g2-tender-review.pages.dev](https://g2-tender-review.pages.dev). Team only, behind a Cloudflare Access email login. It shows every eTenders award ranked by risk score, with the rule-by-rule evidence, and is rebuilt on every merge to `main`. It is a review tool for the detection engine, not the public dashboard.

To preview it locally with real data:

```bash
uv run python scripts/build_review_data.py --ocds path/to/full.jsonl.gz --out review-site/data
uv run python -m http.server 8787 --bind 127.0.0.1 --directory review-site
```

The OCDS file is the [eTenders bulk download](https://data.open-contracting.org/en/publication/143/download?name=full.jsonl.gz) (12 MB).

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
  frontend/      Dashboard
review-site/     Detection review page (static; data generated at build time)
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

## Licence

This project is released under the [MIT Licence](LICENSE) for academic and research reuse.

## Status

Active development. Code freeze **Tuesday 27 October 2026, 18:00**; final capstone submission **Thursday 29 October 2026**.

Detection engine: rules R1-R3, R9 and R12 are implemented and run against the real eTenders data. R4-R8, R10, R11 and the Isolation Forest signal are in progress. Per-rule status is in the [rule catalogue](https://github.com/Ronan-R-R/Group2-Public-Tender-Irregularity-Detector/wiki/Rule-Catalogue).
