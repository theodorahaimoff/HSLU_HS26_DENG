# Decision log

Design decisions for the pipeline, with the reason and where the idea comes from.
Newest first within each section. Status is **Decided** unless marked otherwise.

## Source data (19 Oct 2026, after loading 9 October)

### D16 · Keep one copy of exact duplicate rows, stop on conflicting ones
The Ist-Daten file for 9 October contains 32 rows twice, identical in every column (8 journeys of
the S4 at Luzern, Horw, Luzern Allmend/Messe and Kriens Mattenhof). The check for one row per journey
and stop (D10) correctly stopped the load, but it would have failed the same way on every retry and in
every backfill over that day. An exact copy carries no information, so `transport.py` now keeps one
copy and logs how many it removed (`removed 32 exact duplicate rows`, 5,477 rows loaded). Rows with
the same journey and stop but different values still stop the load, because there is no way to tell
which one is right. 10 October had no duplicates. Found by Emre while testing.

## Weather (19 Oct 2026, after the first full runs)

### D15 · Join weather by the scheduled time of the stop event
`staging.stop_events_weather` gives every stop event the weather of its station
(`raw.stops.weather_station`, D4) in the hour of its **scheduled** time: the departure, or the
arrival at the terminus. Every row has a scheduled time, including cancelled trains, which have no
actual time; and the weather in the hour the train should have been there is the weather that could
have delayed or cancelled it.

MeteoSwiss labels each hour by its **end**, in UTC. A train at 07:40 Swiss time falls in the hour
07:00–08:00, labelled 06:00 UTC in summer and 07:00 UTC in winter. The view takes the start of the
local hour, adds one hour and converts it to UTC; tested with summer time, winter time, a cancelled
train, an hour boundary and a train after midnight.

It is a `LEFT JOIN` on station and hour, the key of `raw.weather_hourly`, so a stop event matches at
most one weather row: no row is lost or duplicated, and `transform.py` fails the run if the counts
differ (D7). A train after midnight gets the next calendar day's weather and stays without weather
until that day is loaded.

### D14 · Weather from the "recent" file, the day replaced like transport
For each of the 5 stations, `weather.py` finds the hourly "recent" file (1 January to yesterday,
updated daily, at about 04:40 Swiss time on 19 October) through the STAC API instead of a stored URL
(D8), keeps the hours that belong to the Swiss calendar day and the 7 parameters we need, with the
values unchanged, and replaces the day in one transaction (D10). Reloading picks up MeteoSwiss
corrections. A parameter a station doesn't measure stays NULL (`tre005hn` only at LUZ, snow depth
not at EGO and MOA); validation requires only the five parameters every station measures.
The "historical" files for earlier years are not read yet, so a backfill only works within the
current year.

The timestamps are UTC and mark the end of the hour. Evidence from the files: global radiation peaks
at the 12:00 stamp, and 29 March 2026, the day the clocks changed, still has 24 rows, which a file in
Swiss local time couldn't have. A Swiss calendar day therefore has 24 hours, or 23 and 25 when the
clocks change. Emre tested the script on 16 days, including the 23-hour day, and with deliberately
broken data to confirm that the checks fail.

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
because Ist-Daten publishes yesterday's file. A manual run uses the `operating_day` input, a text
field checked against `YYYY-MM-DD`. It was a `DATE` input first, but Kestra's backfill form sent it
as a UTC timestamp (`2026-10-07T22:00:00.000Z`) and then rejected it, so no backfill execution was
created (found on 19 October).
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
| Missing or renamed column, wrong credentials, a bug | Not on purpose. The script fails with a clear message, but see below |
| Validation failure | No. `validate_day` has no retry: checking the same data again gives the same answer |

The retry is set on the Kestra task, and Kestra can't tell a temporary failure from a permanent one.
So a permanent error in an ingestion task also runs all three attempts, fails the same way each time
(on 9 October: three downloads of 681 MB), and then fails the run. No data changes, because every
attempt rolls back (D10). The scripts themselves never retry.

### D8 · Check the source first, validate after loading
The daily flow is `check_transport_source → ingest_transport → ingest_weather → validate_day → transform`.
The check finds the day's file link on the dataset page before anything is downloaded. The server
refuses `HEAD` requests (403), so unlike the course's `check_source.py` the check uses a streamed
`GET` that reads only the headers. The service points file is found the same way: its download URL
changes when the file is republished (the URL from 11 October returned 404 on 15 October), so no
script stores a fixed download URL.
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
- Republished files: the Ist-Daten file for 13 October changed again on 15 October. Reloading the
  day before yesterday as well would pick up such corrections. (The 09:00 schedule itself is safe:
  transport is there by about 05:15, weather by about 04:40.)
- Comparing like with like: in the first eight days, weekends had far fewer late departures than
  weekdays, a bigger difference than between wet and dry days. Proposal: compare weather conditions
  within the same day type and hour of day, not across all trains.
- Frost and ice without ground temperature: `tre005hn` (5 cm above grass) is only measured at LUZ.
  Proposal (Emre): use the ground temperature where it exists and the air temperature (`tre200hn`)
  at the other four stations, and document that frost is less precise there.