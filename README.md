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

To be determined.

## Repository Structure

```
docs/            Dissertation chapters, trackers, admin artefacts (mirrors CTU Capstone Project Pack)
src/
  ingestion/     Scrapy + Playwright spiders for eTenders and CIPC
  detection/     Rules engine and Isolation Forest scoring
  api/           FastAPI backend
  frontend/      React dashboard
tests/           Test suites
scripts/         One-off and operational scripts
```

## Getting Started

Under development still.

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
