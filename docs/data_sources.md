# Data Sources

This document describes provenance, access method, format, schema, update frequency,
volume and data-quality risks for each source. Items marked **(to verify)** will be
confirmed during the profiling step before the midterm.

---

## Source evaluation summary

| Question | Ist-Daten v2 | Service Points v2 | MeteoSwiss SwissMetNet |
|---|---|---|---|
| Source type | Operators' customer information systems, published as files | National stop master data (atlas), published as files | Automatic sensor network, published as files via STAC API |
| What does one row represent? | One stop event: one journey at one stop on one operating day | One currently valid service point (stop) | One station × one time interval (we use hourly) |
| How often / how much? | One file per day for all of Switzerland; about 2.2 million rows per day | Daily current-state file; small (51 relevant rows) | Hourly values per station; small |
| Persisted or ephemeral? | Persisted: monthly archive back to 2016 | Persisted; an "all versions" file keeps the history, we use the current-state file | Persisted: historical, recent and now files |
| Schema enforced? | No: CSV has a structure but types are not enforced (dates as text, flags as strings), so schema is applied and validated in our pipeline (schema-on-read) | No (CSV), validated in our pipeline | No (CSV), validated in our pipeline |
| Schema changes | v1 → v2 in 2025/2026 (new identifiers, foreign stops) | v1 → v2 in 2026 | New parameters/stations possible |
| Load pattern | Incremental: one new file per day (delta of the completed day), backfill from archive | Full snapshot, reloaded periodically | Historical full load once, then incremental daily; recent values may be revised |
| Load on source | One download per day | One download per week | Few requests per day; MeteoSwiss terms of use prohibit excessive downloading |

## 1. Ist-Daten v2 (actual train operations)

| Aspect | Description |
|---|---|
| Provider | Open Data Platform Mobility Switzerland, operated by SBB on behalf of the Federal Office of Transport |
| Dataset | [Ist-Daten v2](https://data.opentransportdata.swiss/dataset/ist-daten-v2) – [cookbook](https://opentransportdata.swiss/en/cookbook/historic-and-statistics-cookbook/actual-data/) |
| Content | Every stop event of every journey in Switzerland: scheduled and actual/forecast arrival and departure times, cancellation flag |
| Access | HTTPS download of one CSV per operating day (current month); monthly ZIP files at [archive.opentransportdata.swiss](https://archive.opentransportdata.swiss/) for historical data |
| Format | CSV |
| Update frequency | Daily, for the previous operating day; archive updated by the first working day of the following month |
| Volume | One file per day for all of Switzerland: about 2.2 million rows (sample day, September 2026). Only a small fraction is rail in the canton of Lucerne (Luzern station alone: about 1,000 rows per day). |
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
| `AN_PROGNOSE_STATUS`, `AB_PROGNOSE_STATUS` | Source of the actual time: `REAL` = measured, `PROGNOSE` = last unconfirmed forecast; empty if there is no real-time value | Data-quality filter: delays only from `REAL` |
| `FAELLT_AUS_TF` | Cancelled (true/false) | Cancellation analysis |
| `ZUSATZFAHRT_TF` | Additional (unscheduled) journey | Possible exclusion |
| `DURCHFAHRT_TF` | Pass-through without stop | Exclusion |

### Data-quality risks

- **Missing journeys:** journeys without real-time data are not included at all, so they cannot be detected as missing values in the file.
- **Forecast instead of actual:** some times are the last forecast, not a measured actual time. The prognosis status is used to measure and filter this. First exploration: at Luzern almost all actual times are `REAL`.
- **Precision:** scheduled times are given to the minute, actual times (`AN_PROGNOSE`, `AB_PROGNOSE`) to the second.
- **Arrival or departure only:** a row has no scheduled arrival if the journey starts at that stop, and no scheduled departure if it ends there. Luzern is a terminal station, so every row there has only one of the two. This is not missing data; it defines the stop role (origin, terminus, intermediate).
- **Schema change:** v1 was discontinued at the end of June 2026; this project uses v2 only (from July 2025) to avoid handling two schemas.
- **Stop identifiers:** `BPUIC` is identical to the service points `number` (e.g. 8505000 = Luzern) and is used as the join key; `SLOID` is not needed.
- **Time zone:** times are local Swiss time; alignment with weather timestamps must handle daylight-saving changes.

### Completeness check (planned)

Before the midterm, a profiling script computes, for Lucerne rail data per operator, the
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
| Access | CSV download |
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
| Update frequency | Files split into *historical* (from station start until end of last year, updated yearly), *recent* (1 January of the current year until yesterday, updated daily) and *now* (frequent update) |
| Stations | 5 stations, chosen by the stop-to-station mapping below: Luzern (LUZ), Egolzwil (EGO), Mosen (MOA), Schüpfheim (SPF), Cham (CHZ, canton Zug) |
| Volume | Small: a few stations × hourly values |
| Licence | Free use; **source must be cited ("Source: MeteoSwiss")** |

### Metadata files

| File | Content | Use |
|---|---|---|
| `ogd-smn_meta_stations.csv` | All stations with abbreviation, name, canton, altitude and WGS84 coordinates | Stop-to-station mapping |
| `ogd-smn_meta_parameters.csv` | Parameter codes with description, granularity and unit | Choosing the parameters |
| `ogd-smn_meta_datainventory.csv` | Which station measures which parameter, and since when | Checking that each chosen station measures all needed parameters **(to verify: a complete download is still needed)** |

The files are semicolon-separated and Latin-1 encoded (except the inventory file).

### Parameters (hourly)

| Code | Description | Unit | Used for |
|---|---|---|---|
| `rre150h0` | Precipitation, hourly total | mm | Rain; snow and icy conditions (with temperature) |
| `tre200h0` | Air temperature 2 m, hourly mean | °C | Heat, frost, snow/ice derivation |
| `tre200hn` / `tre200hx` | Air temperature 2 m, hourly minimum / maximum | °C | Frost / heat |
| `tre005hn` | Air temperature 5 cm above grass, hourly minimum | °C | Ground frost, icy conditions |
| `fu3010h1` | Gust peak (1 s), hourly maximum | km/h | Wind, thunderstorm proxy |
| `htoauths` | Snow depth, automatic measurement | cm | Supporting only: not quality-checked by MeteoSwiss |

Not available in the station data: warning levels, hail and lightning. Thunderstorms are
therefore approximated from rain intensity and gusts.

### Stop-to-station mapping

No source links stops to weather stations, so the pipeline derives the mapping:

1. Compute the distance from each of the 51 stops (service points `wgs84North`/`wgs84East`) to every station in `ogd-smn_meta_stations.csv` (158 stations, no pre-filter needed).
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

### Data-quality risks

- **Snow:** automatic snow-depth data is not manually checked and is not an official series; snow is therefore derived from precipitation and temperature.
- **Representativeness:** five stations cannot capture local conditions at every stop (e.g. valleys vs. lake area); distance and altitude difference are stored per stop so weak matches can be identified.
- **Missing values / outages:** individual hours may be missing and must be handled explicitly.
- **Revisions:** recent data may be corrected later; ingestion must be rerunnable so that corrected values replace old ones.
- **Time zone:** MeteoSwiss timestamps are expected to be UTC **(to verify)**; conversion to Swiss local time is required for joining.