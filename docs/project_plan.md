# Project Plan and Backlog

## Milestones

| Week | Milestone | Deliverable / deadline |
|---|---|---|
| 3 | Initial pitch | README, data sources, use case, Architecture v0.1, this plan; 5-min pitch |
| 6 | Midterm submission | Repository link + commit hash/tag via ILIAS, **Thu 22 Oct 2026, 15:30** |
| 7 | Midterm defence | 10-min question-only oral defence |
| 9 | Midterm peer reviews | Two review documents via ILIAS, **12 Nov 2026** |
| 13 | Final submission | Repository link + commit hash/tag via ILIAS, **Thu 10 Dec 2026, 20:00** |
| 14 | Final defence | 10-min question-only oral defence |
| – | Final peer reviews | Two review documents via ILIAS, **31 Dec 2026** |

## Backlog

A = Emre Sen, B = Theodora Haimoff. Completed items are checked off in this file.

### Milestone 1 – Initial pitch (Week 3)

- [x] Create repository, grant access to instructors (B)
- [x] README, use case and data source documentation (A + B)
- [x] Architecture v0.1 and division of responsibilities (A + B)
- [x] Download sample Ist-Daten day and MeteoSwiss station file; confirm access works (A + B)
- [x] Prepare 5-minute pitch, both members presenting (A + B)

### Midterm – Local pipeline (Weeks 4–6)

- [x] Data exploration notebook linking every data decision to evidence (B)
- [x] Stop list in code: download service points, apply the documented filters, check 51 stops (B)
- [x] Stop-to-weather-station mapping in code (nearest station, max. 300 m altitude difference) (B)
- [x] Confirm the 5 stations measure all needed parameters (checked in the loaded hourly files) (A)
- [x] Source check and transport ingestion: one day, filtered, loaded into PostgreSQL (B)
- [x] Weather ingestion script: recent hourly files into PostgreSQL, one day per run (A)
- [x] Docker Compose: PostgreSQL, pgAdmin, Kestra and its database on a shared network; pipeline image (B)
- [x] Kestra flows: stop list and daily transport run tested (B); full run with weather, rerun and backfill (A + B)
- [x] Idempotent reruns for transport: the day is replaced in one transaction (B); weather the same way (A)
- [x] Validation after each load and verification queries for reviewers (B)
- [x] First justified transformation: staging view with stop role, time basis and arrival/departure delay from `REAL` times, every row kept (B). Weather join by scheduled hour in a second staging view (A + B)
- [x] `.env.example`, `.gitignore`, setup/run/verify instructions in README (A + B)
- [x] Architecture v0.2 with changed decisions (B; weather details by A)
- [ ] Test reproducibility from a fresh clone before submission (A)

### Final – Cloud pipeline (Weeks 8–13)

- [ ] Terraform: GCS bucket and BigQuery dataset (A)
- [ ] Profiling script: completeness of Lucerne rail data per operator, arrivals and departures separately (B)
- [ ] Transport backfill from monthly archive (B)
- [ ] dbt models for staging and curated tables (A + B)
- [ ] Ingestion writes directly to GCS (no local dependency) (A)
- [ ] Load raw data from GCS into BigQuery staging (B)
- [ ] Weather type and severity classification (B)
- [ ] Curated tables with documented grain (fact / dimensions / aggregate) (A + B)
- [ ] Partitioning and clustering based on query patterns (A)
- [ ] Data-quality checks (e.g. duplicates, missing hours, share of forecast-only times) (B)
- [ ] Verification queries answering the analytical questions (A + B)
- [ ] Final architecture incl. evolution from v0.1 (A + B)
- [ ] Streamlit dashboard: findings view on the aggregate table (B)
- [ ] Streamlit dashboard: current-risk view with latest MeteoSwiss measurement (B)
- [ ] Dashboard container in Docker Compose, documented setup (A + B)
- [ ] Known limitations documented (A + B)
- [ ] Reproducibility test from a fresh clone (A + B)

### Optional (only if time allows)

- [ ] Extend to additional regions or transport modes