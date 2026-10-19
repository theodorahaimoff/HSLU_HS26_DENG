# Data Sources

This document describes provenance, access method, format, schema, update frequency,
volume and data-quality risks for each source. The figures were checked against real files in
[notebooks/01_explore_sources.ipynb](../notebooks/01_explore_sources.ipynb) (operating days
8 October and 29 September 2026); the weather figures against the loaded hourly files
(8 and 11–18 October 2026).

---

## Source evaluation summary

| Question | Ist-Daten v2 | Service Points v2 | MeteoSwiss SwissMetNet |
|---|---|---|---|
| Source type | Operators' customer information systems, published as files | National stop master data (atlas), published as files | Automatic sensor network, published as files via STAC API |
| What does one row represent? | One stop event: one journey at one stop on one operating day | One currently valid service point (stop) | One station × one time interval (we use hourly) |
| How often / how much? | One file per day for all of Switzerland; about 2.6 million rows (658 MB) per day | Daily current-state file, about 60,000 rows (27 MB), 51 relevant | Hourly values per station; small |
| Persisted or ephemeral? | Persisted: monthly archive back to 2016 | Persisted; an "all versions" file keeps the history, we use the current-state file | Persisted: historical, recent and now files |
| Schema enforced? | No: CSV has a structure but types are not enforced (dates as text, flags as strings), so schema is applied and validated in our pipeline (schema-on-read) | No (CSV), validated in our pipeline | No (CSV), validated in our pipeline |
| Schema changes | v1 → v2 in 2025/2026 (new identifiers, foreign stops) | v1 → v2 in 2026 | New parameters/stations possible |
| Load pattern | Batch, pull, full load of each day's file, replacing that day (not CDC); backfill from the archive | Full snapshot, reloaded when the stops change | Historical full load once, then daily; the day is reloaded so revisions are picked up |
| Load on source | One download per day | On demand (setup flow) | Few requests per day; MeteoSwiss terms of use prohibit excessive downloading |

## 1. Ist-Daten v2 (actual train operations)

| Aspect | Description |
|---|---|
| Provider | Open Data Platform Mobility Switzerland, operated by SBB on behalf of the Federal Office of Transport |
| Dataset | [Ist-Daten v2](https://data.opentransportdata.swiss/dataset/ist-daten-v2) – [cookbook](https://opentransportdata.swiss/en/cookbook/historic-and-statistics-cookbook/actual-data/) |
| Content | Every stop event of every journey in Switzerland: scheduled and actual/forecast arrival and departure times, cancellation flag |
| Access | HTTPS download of one CSV per operating day. The dataset page lists a rolling window of the last 50 days; each file has its own resource ID, so the link is read from the page. Older days: monthly **v2** ZIPs (`ist-daten-v2-YYYY-MM.zip`) at [archive.opentransportdata.swiss](https://archive.opentransportdata.swiss/actual_data_archive.htm), identical to the daily files (checked for 29 September 2026) |
| Format | CSV |
| Update frequency | Daily, for the previous operating day, available by about 05:15 Swiss time; files can be republished later. Archive updated by the first working day of the following month |
| Volume | One file per day for all of Switzerland: about 2.6 million rows, 658 MB (8 October 2026). Rail at our 51 stops: 5,532 rows (0.21 %); Luzern station alone: 842 rows. |
| Scope used | Rail (`PRODUKT_ID = Zug`) at stops in the canton of Lucerne, from July 2025 |

### Relevant fields

| Field | Meaning | Use |
|---|---|---|
| `BETRIEBSTAG` | Operating day (DD.MM.YYYY) | Partition / date key |
| `FAHRT_BEZEICHNER` | Journey identifier | Part of the event key |
| `BETREIBER_ABK`, `BETREIBER_NAME` | Operator | Analysis dimension |
| `PRODUKT_ID` | Product type (train, bus, …) | Filter to rail |
| `LINIEN_TEXT`, `VERKEHRSMITTEL_TEXT` | Line and train category (e.g. S, IR) | Analysis dimension |
| `BPUIC`, `HALTESTELLEN_NAME`, `SLOID` | Stop identifiers and name | Join to stop metadata (`BPUIC` = service points `number`) |
| `ANKUNFTSZEIT`, `ABFAHRTSZEIT` | Scheduled arrival / departure | Delay calculation |
| `AN_PROGNOSE`, `AB_PROGNOSE` | Actual or last forecast arrival / departure | Delay calculation |
| `AN_PROGNOSE_STATUS`, `AB_PROGNOSE_STATUS` | Source of the actual time: `REAL` = measured, `PROGNOSE` = last unconfirmed forecast, `UNBEKANNT` (undocumented) = exactly the cancelled trains; empty if there is no scheduled time | Flag per row; delays only from `REAL` (other rows are kept with a NULL delay) |
| `FAELLT_AUS_TF` | Cancelled (true/false) | Cancellation analysis |
| `ZUSATZFAHRT_TF` | Additional (unscheduled) journey | Possible exclusion |
| `DURCHFAHRT_TF` | Pass-through without stop | Exclusion |

### Data quality and how we handle it

| What we found | How the pipeline handles it |
|---|---|
| **Forecasts instead of measurements:** on 8 October, `REAL` (measured) about 88 %, `UNBEKANNT` about 11 % (exactly the cancelled trains), `PROGNOSE` 40 rows | Every row gets a status; delays are computed only from `REAL` times, the other rows are kept with a NULL delay, so every exclusion stays countable (D7) |
| **Arrival or departure only:** a journey that starts at a stop has no arrival time there, one that ends has no departure. Luzern is a terminal station (113 of 842 rows have both, for trains that reverse) | Not missing data: it defines the stop role (origin, terminus, intermediate), and arrivals and departures are analysed separately (D2) |
| **Planned closures:** cancellations carry no cause; on 8 October, 496 of 558 cancellations at our stops were the whole S9 line | Rule for line-wide closures being defined; those rows are kept but left out of the weather comparison |
| **Missing journeys:** journeys without real-time data are not in the file at all | Can't be detected as missing values; documented as a limitation. The completeness check below measures it per operator |
| **Precision:** scheduled times to the minute, actual times to the second | Delays are computed in minutes with two decimals |
| **Exact duplicate rows:** the file for 9 October has 32 rows twice, identical in every column (8 S4 journeys) | One copy is kept and the number removed is logged; rows with the same journey and stop but different values still stop the load (D16) |
| **Inconsistent product codes:** `Bus` and `BUS` in the same file | The rail filter compares case-insensitively |
| **Stop identifiers:** v2 lets some operators deliver the SLOID in the `BPUIC` field | Checked on two days: the `BPUIC` filter missed no rail row at our stops, so `BPUIC` = service points `number` is the join key |
| **Schema change:** v1 was discontinued at the end of June 2026 | We use v2 only (from July 2025), one schema |
| **Changing download links:** each file has its own resource ID | Links are read from the dataset page on every run; the source check fails with a clear message if the page changes (D8) |
| **Time zone:** times are Swiss local time | Converted to the UTC hour labels of the weather data in the staging join (D15) |

### Completeness check (planned for the final)

A profiling script computes, for Lucerne rail data per operator, the
share of stop events that have a scheduled time but no `REAL` actual time (separately for
arrivals and departures, so that origin/terminus rows are not counted as missing). If an
operator falls below a documented threshold (e.g. 95 % complete), it is excluded and the
decision is documented.

## 2. Stop metadata (Service Points v2)

| Aspect | Description |
|---|---|
| Provider | opentransportdata.swiss (master data from the national service-point register, atlas) |
| Dataset | [Service Points v2](https://data.opentransportdata.swiss/dataset/service-point-v2) – [cookbook](https://opentransportdata.swiss/en/cookbook/masterdata-cookbook/servicepoints/). The previous service-points datasets were discontinued at the end of June 2026. |
| Content | All public-transport service points in Switzerland (stops, operating points, bus stops) with number, official designation, canton, municipality, means of transport, WGS84 coordinates and height |
| Access | CSV download. The file gets a new resource ID when it is republished, so the link is read from the [dataset page](https://data.opentransportdata.swiss/dataset/service-point-v2) on every run (a stored URL from 11 October returned 404 on 15 October) |
| File used | `actual-date-swiss-service-point.csv`: only the currently valid version of each service point (one row per stop). The "all versions" file contains one row per historical version (`validFrom`/`validTo`) and is not used. |
| Use | Select the rail stops in the canton of Lucerne; assign each stop to the nearest weather station; join to Ist-Daten via `BPUIC` = `number` |
| Update frequency | Daily; treated as a slowly changing reference table (full reload) |

### Filters (applied in code)

The pipeline downloads the full file and applies these filters itself, so the stop list is
reproducible without any manual export:

| Filter | Reason |
|---|---|
| `cantonAbbreviation = 'LU'` | Scope: canton of Lucerne (calculated by atlas from the coordinates) |
| `stopPoint = true` | Only real stops where passengers board, no technical or freight operating points |
| `hasGeolocation = true` | Coordinates are needed for the weather-station mapping |
| `meansOfTransport` contains `TRAIN` | The file also contains bus stops; "contains" because a stop can list several modes |

Result during exploration: **51 rail stops**. The pipeline should check this count.

**Simplification:** the current-state file is used for the whole analysis period. Name,
location and canton of a station practically never change, so a per-day historical
version is not needed.

## 3. MeteoSwiss – automatic weather stations (SwissMetNet)

| Aspect | Description |
|---|---|
| Provider | Federal Office of Meteorology and Climatology MeteoSwiss (Open Government Data since 2025) |
| Documentation | [MeteoSwiss Open Data – automatic weather stations](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations) |
| Access | STAC API of the Federal Spatial Data Infrastructure: `https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-smn` (and `ch.meteoschweiz.ogd-smn-precip` for precipitation-only stations) |
| Format | CSV, one file per station and granularity |
| Granularity used | Hourly (official MeteoSwiss aggregates, not self-computed) |
| Update frequency | Files split into *historical* (from station start until end of last year, updated yearly), *recent* (1 January of the current year until yesterday, updated daily, at about 04:40 Swiss time on 19 October 2026) and *now* (frequent update). We use the *recent* files |
| Stations | 5 stations, chosen by the stop-to-station mapping below: Luzern (LUZ), Egolzwil (EGO), Mosen (MOA), Schüpfheim (SPF), Cham (CHZ, canton Zug) |
| Volume | 120 rows per day for our 5 stations (24 hours each); one "recent" file per station covers 1 January to yesterday |
| Licence | Free use; **source must be cited ("Source: MeteoSwiss")** |

### Metadata files

| File | Content | Use |
|---|---|---|
| `ogd-smn_meta_stations.csv` | All stations with abbreviation, name, canton, altitude and WGS84 coordinates | Stop-to-station mapping |
| `ogd-smn_meta_parameters.csv` | Parameter codes with description, granularity and unit | Choosing the parameters |
| `ogd-smn_meta_datainventory.csv` | Which station measures which parameter, and since when | Which station measures which parameter (see the coverage below) |

The files are semicolon-separated and Windows-1252 encoded, a superset of Latin-1 (except the inventory file).

### Parameters (hourly)

| Code | Description | Unit | Used for |
|---|---|---|---|
| `rre150h0` | Precipitation, hourly total | mm | Rain; snow and icy conditions (with temperature) |
| `tre200h0` | Air temperature 2 m, hourly mean | °C | Heat, frost, snow/ice derivation |
| `tre200hn` / `tre200hx` | Air temperature 2 m, hourly minimum / maximum | °C | Frost / heat |
| `tre005hn` | Air temperature 5 cm above grass, hourly minimum | °C | Ground frost, icy conditions |
| `fu3010h1` | Gust peak (1 s), hourly maximum | km/h | Wind, thunderstorm proxy |
| `htoauths` | Snow depth, automatic measurement | cm | Supporting only: not quality-checked by MeteoSwiss |

Coverage in the loaded hourly files (8 and 11–18 October 2026): all 5 stations measure `rre150h0`,
`tre200h0`, `tre200hn`, `tre200hx` and `fu3010h1`. `tre005hn` is only measured at LUZ, and `htoauths`
not at EGO and MOA; these stay NULL there.

Not available in the station data: warning levels, hail and lightning. Thunderstorms are
therefore approximated from rain intensity and gusts.

### Stop-to-station mapping

No source links stops to weather stations, so the pipeline derives the mapping:

1. Compute the distance from each of the 51 stops (service points `wgs84North`/`wgs84East`) to every station in `ogd-smn_meta_stations.csv` (159 stations on 15 October 2026, no pre-filter needed).
2. Exclude stations whose altitude differs by more than 300 m from the stop (`height` vs. `station_height_masl`). Without this rule, Malters and Schachen would be mapped to Pilatus (2,105 m) and the Wolhusen area to Napf (1,404 m).
3. Assign the nearest remaining station and store it with the distance and altitude difference.

Result during exploration:

| Station | Stops | Area |
|---|---|---|
| Luzern (LUZ) | 20 | Lucerne, Emmenbrücke, Kriens, Meggen, Ebikon, Malters, Sempach |
| Egolzwil (EGO) | 15 | Sursee, Willisau, Reiden, Dagmersellen, Wauwil |
| Mosen (MOA) | 8 | Seetal (Hochdorf, Hitzkirch, Baldegg) |
| Schüpfheim (SPF) | 6 | Entlebuch line (Entlebuch, Escholzmatt, Wolhusen) |
| Cham (CHZ, canton Zug) | 2 | Gisikon-Root, Ballwil |

The canton is deliberately not used: Cham is outside the canton but closer to two stops than
any Lucerne station. All stops are within 14 km of their station; the weakest matches are
Wolhusen and Werthenstein (13–14 km, up to 190 m altitude difference).

### Data quality and how we handle it

| What we found | How the pipeline handles it |
|---|---|
| **Snow:** automatic snow depth is not quality-checked by MeteoSwiss and is not an official series | Loaded for reference only; snow is derived from precipitation and temperature |
| **Representativeness:** five stations can't capture local conditions at every stop (valleys vs. lake area) | Distance and altitude difference are stored per stop, so weak matches can be identified (D4) |
| **Missing hours or values** | Ingestion fails if a station doesn't have every hour of the day; validation checks the core parameters and plausible ranges |
| **Revisions:** recent values may be corrected later | Each run replaces the whole day, so corrected values replace old ones (D14) |
| **Time zone:** timestamps are UTC and mark the **end** of the hour. Verified: global radiation peaks at the 12:00 stamp, and 29 March 2026, the day the clocks changed, has 24 rows | Ingestion assigns each hour to the Swiss calendar day it starts in; the staging join converts the train time to the matching hour (D15) |