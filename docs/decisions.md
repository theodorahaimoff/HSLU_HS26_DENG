# Decision log

Design decisions for the pipeline, with the reason and where the idea comes from.
Newest first within each section. Status is **Decided** unless marked otherwise.

## History (15 Oct 2026, after checking the archive)

### D13 · History from the monthly v2 archive, recent days from the daily files
The dataset page only keeps a rolling window of 50 daily files. Older days come from
[archive.opentransportdata.swiss](https://archive.opentransportdata.swiss/): one ZIP per month with all
daily files of that month, from 2016 to the last complete month. We use the **v2** ZIPs
(`ist-daten-v2-YYYY-MM.zip`), which have the same format as our daily files. v2 starts on
13 July 2025, so one year of history is October 2025 to September 2026.

Checked on September 2026 (`notebooks/01_explore_sources.ipynb`):
- 30 daily files, no missing days, one operating day per file, the same columns as the daily file;
- the archive file for 2026-09-29 is **identical** to the daily file for that day
  (2,614,536 rows, 5,419 stop events for our stops, 0 differing values);
- the BPUIC filter misses no rows at our stops (SLOID check: 0).

One loader, two download paths: the backfill reads each daily CSV straight from the ZIP
(nothing is unpacked; about 12 s per day), applies the same filter and the same replace-the-day load
(D10), and deletes the ZIP before the next month. About 16 GB of downloads and about 1.2 h of
reading for a year. File names differ in case (`IstDaten` in the archive, `istdaten` daily),
so the loader matches them case-insensitively.

**Download:** the backfill script downloads the ZIPs itself from
[archive.opentransportdata.swiss/actual_data_archive.htm](https://archive.opentransportdata.swiss/actual_data_archive.htm).
The platform's [terms of use](https://opentransportdata.swiss/en/terms-of-use/) describe the data as
freely available in machine-readable format; request limits and registration only apply to the API
services, not to file downloads. Obligation: cite opentransportdata.swiss as the source. The script is
a considerate client: one ZIP at a time, retries with a pause, each month downloaded once.

**Scope:** the full year is a one-off load for the final. The midterm backfill uses daily files
(the last 50 days), and the README asks peer reviewers to backfill two or three days, not the archive.

## Orchestration and reliability (15 Oct 2026, after the Week 5 lab)

### D12 · Kestra as the orchestrator
Kestra runs, schedules and records every pipeline run. It is the tool taught in Week 5, so our setup
follows the course lab: Kestra plus its own metadata database (`kestra-db`) next to our data database,
and each task runs our Python code in a temporary container built from our own image.
Kestra coordinates; our scripts do the work. Every script also runs without Kestra.

### D11 · One operating day per run, chosen by the scheduled date
Each script takes `--date YYYY-MM-DD`. A scheduled run processes the day before `trigger.date`,
because Ist-Daten publishes yesterday's file. A manual run uses the `operating_day` input.
The scripts never use the machine's current date, so a backfill over past dates processes exactly
those days. Backfill and retry are different things: a backfill processes a missed historical day,
a retry repeats a failed attempt at the same day.

### D10 · Replace the day inside one transaction
Loading a day deletes that day's rows and inserts the new ones inside one database transaction
(`with engine.begin()`), following the course loader `ingest_months.py`:
the connection is tested before downloading, the table is locked with a short `lock_timeout` so two
runs can't replace the same day at once, and the committed row count is compared with the filtered
source count. Any mismatch or error rolls back, and the previous version of the day stays.
A rerun therefore never creates duplicates, and corrected source data replaces the old values.

### D9 · Retry temporary failures only
| Failure | Retry? |
|---|---|
| Yesterday's file not published yet | Yes, `check_transport_source`: every 30 min, 4 attempts |
| Network or database connection error | Yes, ingestion tasks: every 2 min, 3 attempts |
| Missing or renamed column, wrong credentials, a bug | No. The script fails with a clear message |
| Validation failure | No. Checking the same data again gives the same answer |

### D8 · Check the source first, validate after loading
The daily flow is `check_transport_source → ingest_transport → ingest_weather → validate_day`.
The check finds the day's file link on the dataset page before anything is downloaded. The server
refuses `HEAD` requests (403), so unlike the course's `check_source.py` the check uses a streamed
`GET` that reads only the headers.
Validation fails the execution, it never only warns: the day has rows, every stop has a weather
station, and every flag and status column only holds expected values.

## Data quality and transformation (15 Oct 2026, from Week 4)

### D7 · Flag rows instead of dropping them
No row is silently removed. Rows without a measured time and cancelled trains stay in the data with
a status column. Exploration showed that `UNBEKANNT` (undocumented, about 11 %) is exactly the
status of cancelled trains, and `PROGNOSE` (under 1 %) is an unconfirmed forecast for a train that ran. Delay values are only computed from `REAL` times and
are NULL otherwise. The reviewed table has the same row count as the loaded table, and every
exclusion can be counted. This follows the Week 4 `report_status` pattern.

### D6 · Filter to our stops at ingestion, keep everything else unchanged
A daily Ist-Daten file is about 2.6 M rows and 658 MB, too much to keep a year of it in local
PostgreSQL. Ingestion keeps only rows for our 51 stops and trains (product compared
case-insensitively), with every column unchanged. All cleaning and flagging happens afterwards.
**Final version (open):** keep the full daily file in GCS as the raw zone, converted to Parquet,
so curated tables can be rebuilt after a rule changes (Week 6).

## Ingestion design (Week 4 terms)

### D5 · Batch, pull, full load per period. Not CDC
| Source | Timing | Control | Scope |
|---|---|---|---|
| Ist-Daten v2 | Batch, daily | Pull | Full load of each day's file, replacing that day |
| Service Points v2 | Batch, rarely | Pull | Full snapshot of the stop list |
| SwissMetNet | Batch, daily | Pull | Reload the day, so MeteoSwiss corrections are picked up |

Daily freshness is enough: the users look at historical patterns, and no action becomes impossible
if data is a day old. Streaming would add cost and complexity without benefit.

## Earlier decisions (pitch and exploration)

- **D4** Stops mapped to the nearest SwissMetNet station, skipping stations with more than 300 m
  altitude difference. Result: LUZ, EGO, MOA, SPF, CHZ.
- **D3** Service points filtered in code (canton LU, stop point, geolocation, TRAIN), never from a
  GUI export. Ist-Daten `BPUIC` joins to the service point `number`.
- **D2** Separate `arrival_delay` and `departure_delay`, plus a stop role (origin, terminus,
  intermediate). Luzern is mostly a terminus or origin, but some trains reverse there and have both.
- **D1** Canton Lucerne, rail only, hourly weather. Analytical use case, no machine learning.

## Still to agree

- Delay threshold for "delayed" (proposal: 3 minutes or more, like SBB's punctuality figure) and
  arrival delay as the main measure, departure delay as a second one.
- Planned closures: on 8 October, 496 of 558 cancellations were the whole S9 line. Proposal: mark a
  line on a day as a closure when nearly all its trips are cancelled, keep the rows with a status,
  and leave them out of the weather comparison. Check two or three more days first.
- History to load: one year (October 2025 to September 2026) is now possible from the v2 archive
  (D13). Midterm: a few days plus a short backfill; the full year belongs to the final.
- Schedule time: yesterday's file is there by about 05:15 Swiss time, so the 09:00 placeholder is
  safe. Files can be republished later (the file for 13 October changed again on 15 October);
  reloading the day before yesterday as well would pick up such corrections.