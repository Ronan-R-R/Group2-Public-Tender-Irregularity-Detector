# Public Tender Irregularity Detector

> **CTU SE2 Capstone Project - Group 2, Boksburg Campus (2026)**
> A civic-technology platform that cross-references South African public tender awards with company and director registries to flag patterns consistent with procurement irregularity.

---

## About This Project

South Africa loses tens of billions of rands annually through irregular, wasteful, and corrupt public procurement. The National Treasury publishes every awarded tender on the [eTenders portal](https://www.etenders.gov.za/), and the Companies and Intellectual Property Commission (CIPC) maintains a public register of companies and directors. No publicly available tool currently joins these datasets and applies automated red-flag detection to the result.

This project closes that gap. It ingests tender award data continuously, enriches each award with director and company information from CIPC, applies a rules engine built on the Transparency International and World Bank red-flag frameworks, and surfaces a per-tender risk score with full rule-level transparency.

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

Nothing runs as a hosted server. The scheduled workflow scrapes, scores, writes to Supabase and publishes static JSON for the dashboard.

## Repository Structure

```
docs/            Dissertation chapters and assessment artefacts (design docs live in the GitHub Wiki)
src/
  ingestion/     Tender and company data collection
  detection/     Red-flag rules, composite risk score, Isolation Forest
  db/            PostgreSQL schema
  api/           FastAPI app for local use and the demo
  frontend/      Dashboard
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
- **Methodology:** Agile Scrum, two-week sprints

## Key Data Sources

- [National Treasury eTenders Portal](https://www.etenders.gov.za/)
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

Active development. Final capstone submission: **29 October 2026**.
