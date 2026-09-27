# Project Plan and Backlog

## Milestones

| Week | Milestone | Deliverable / deadline |
|---|---|---|
| 3 | Initial pitch | README, data sources, use case, Architecture v0.1, this plan; 10-min pitch |
| 6 | Midterm submission | Repository link + commit hash/tag via ILIAS, **Thu 22 Oct 2026, 15:30** |
| 7 | Midterm defence | 10-min question-only oral defence |
| 9 | Midterm peer reviews | Two review documents via ILIAS, **12 Nov 2026** |
| 13 | Final submission | Repository link + commit hash/tag via ILIAS, **Thu 10 Dec 2026, 20:00** |
| 14 | Final defence | 10-min question-only oral defence |
| – | Final peer reviews | Two review documents via ILIAS, **31 Dec 2026** |

## Backlog

A = Emre Sen, B = Theodora Haimoff. Completed items are checked off in this file.

### Milestone 1 – Initial pitch (Week 3)

- [ ] Create repository, grant access to instructors (A)
- [ ] README, use case and data source documentation (A + B)
- [ ] Architecture v0.1 and division of responsibilities (A + B)
- [ ] Download sample Ist-Daten day and MeteoSwiss station file; confirm access works (A + B)
- [ ] Prepare 10-minute pitch, both members presenting (A + B)

### Midterm – Local pipeline (Weeks 4–6)

- [ ] Profiling script: completeness of Lucerne rail data per operator (A)
- [ ] Identify Lucerne rail stops and assign nearest weather station (A)
- [ ] Transport ingestion script: one day, filtered, loaded into PostgreSQL (A)
- [ ] Transport backfill from monthly archive (A)
- [ ] Weather ingestion script: historical + recent hourly files into PostgreSQL (B)
- [ ] Docker Compose: PostgreSQL + orchestrator on a shared network (A)
- [ ] Choose orchestrator; daily schedule, retries, backfill for both sources (B)
- [ ] Idempotent reruns (partition overwrite per day/hour) (A + B)
- [ ] First justified transformation: delay calculation + join with hourly weather (B)
- [ ] `.env.example`, `.gitignore`, setup/run/verify instructions in README (A + B)
- [ ] Architecture v0.2 with changed decisions (A + B)
- [ ] Test reproducibility from a fresh clone before submission (A + B)

### Final – Cloud pipeline (Weeks 8–13)

- [ ] Terraform: GCS bucket and BigQuery dataset (A)
- [ ] Ingestion writes directly to GCS (no local dependency) (A)
- [ ] Load raw data from GCS into BigQuery staging (B)
- [ ] Weather type and severity classification (B)
- [ ] Curated tables with documented grain (fact / dimensions / aggregate) (A + B)
- [ ] Partitioning and clustering based on query patterns (A)
- [ ] Data-quality checks (e.g. duplicates, missing hours, share of forecast-only times) (B)
- [ ] Verification queries answering the analytical questions (A + B)
- [ ] Final architecture incl. evolution from v0.1 (A + B)
- [ ] Streamlit dashboard: findings view on the aggregate table (A)
- [ ] Streamlit dashboard: current-risk view with latest MeteoSwiss measurement (B)
- [ ] Dashboard container in Docker Compose, documented setup (A + B)
- [ ] Known limitations documented (A + B)
- [ ] Reproducibility test from a fresh clone (A + B)

### Optional (only if time allows)

- [ ] Extend to additional regions or transport modes
