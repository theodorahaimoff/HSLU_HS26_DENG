# Data Sources

This document describes provenance, access method, format, schema, update frequency,
volume and data-quality risks for each source. Items marked **(to verify)** will be
confirmed during the profiling step before the midterm.

---

## 1. Ist-Daten v2 (actual train operations)

| Aspect | Description |
|---|---|
| Provider | Open Data Platform Mobility Switzerland, operated by SBB on behalf of the Federal Office of Transport |
| Dataset | [Ist-Daten v2](https://data.opentransportdata.swiss/dataset/ist-daten-v2) – [cookbook](https://opentransportdata.swiss/en/cookbook/historic-and-statistics-cookbook/actual-data/) |
| Content | Every stop event of every journey in Switzerland: scheduled and actual/forecast arrival and departure times, cancellation flag |
| Access | HTTPS download of one CSV per operating day (current month); monthly ZIP files at [archive.opentransportdata.swiss](https://archive.opentransportdata.swiss/) for historical data |
| Format | CSV |
| Update frequency | Daily, for the previous operating day; archive updated by the first working day of the following month |
| Volume | One file per day for all of Switzerland; size per day **(to verify)**. Only a small fraction is rail in the canton of Lucerne. |
| Scope used | Rail (`PRODUKT_ID = Zug`) at stops in the canton of Lucerne, from July 2025 |

### Relevant fields

| Field | Meaning | Use |
|---|---|---|
| `BETRIEBSTAG` | Operating day (DD.MM.YYYY) | Partition / date key |
| `FAHRT_BEZEICHNER` | Journey identifier | Part of the event key |
| `BETREIBER_ABK`, `BETREIBER_NAME` | Operator | Analysis dimension |
| `PRODUKT_ID` | Product type (train, bus, …) | Filter to rail |
| `LINIEN_TEXT`, `VERKEHRSMITTEL_TEXT` | Line and train category (e.g. S, IR) | Analysis dimension |
| `BPUIC`, `HALTESTELLEN_NAME`, `SLOID` | Stop identifiers and name | Join to stop metadata |
| `ANKUNFTSZEIT`, `ABFAHRTSZEIT` | Scheduled arrival / departure | Delay calculation |
| `AN_PROGNOSE`, `AB_PROGNOSE` | Actual or last forecast arrival / departure | Delay calculation |
| `AN_PROGNOSE_STATUS`, `AB_PROGNOSE_STATUS` | Whether the value is a real measurement or a forecast | Data-quality filter |
| `FAELLT_AUS_TF` | Cancelled (true/false) | Cancellation analysis |
| `ZUSATZFAHRT_TF` | Additional (unscheduled) journey | Possible exclusion |
| `DURCHFAHRT_TF` | Pass-through without stop | Exclusion |

### Data-quality risks

- **Missing journeys:** journeys without real-time data are not included at all, so they cannot be detected as missing values in the file.
- **Forecast instead of actual:** some times are the last forecast, not a measured actual time. The prognosis status is used to measure and filter this.
- **Precision:** times are given to the minute.
- **Schema change:** v1 was discontinued at the end of June 2026; this project uses v2 only (from July 2025) to avoid handling two schemas.
- **Stop identifiers:** v2 includes stops delivered with the new SLOID identifier; joins to stop metadata must handle both `BPUIC` and `SLOID` **(to verify)**.
- **Time zone:** times are local Swiss time; alignment with weather timestamps must handle daylight-saving changes.

### Completeness check (planned)

Before the midterm, a profiling script computes, for Lucerne rail data per operator:
the share of stop events with a real (not forecast) actual time. If an operator falls
below a documented threshold (e.g. 95 %), it is excluded and the decision is documented.

## 2. Stop metadata (Service Points v2)

| Aspect | Description |
|---|---|
| Provider | opentransportdata.swiss (master data from the national service-point register, atlas) |
| Dataset | [Service Points v2](https://data.opentransportdata.swiss/dataset/service-point-v2) – [cookbook](https://opentransportdata.swiss/en/cookbook/masterdata-cookbook/servicepoints/). The previous service-points datasets were discontinued at the end of June 2026. |
| Content | All public-transport service points in Switzerland (stops and operating points) with identifiers (incl. SLOID), official designation, validity period and WGS84 coordinates |
| Access | CSV download |
| Versions | "Today" (daily updated), "timetable change" and "all versions" (incl. history); this project uses "today" |
| Use | Select stops in the canton of Lucerne; assign each stop to the nearest weather station; join to Ist-Daten via `BPUIC` / `SLOID` |
| Update frequency | Daily; treated as a slowly changing reference table |
| Canton filter | **(to verify)** whether a canton field is included directly or must be derived from coordinates |

## 3. MeteoSwiss – automatic weather stations (SwissMetNet)

| Aspect | Description |
|---|---|
| Provider | Federal Office of Meteorology and Climatology MeteoSwiss (Open Government Data since 2025) |
| Documentation | [MeteoSwiss Open Data – automatic weather stations](https://opendatadocs.meteoswiss.ch/a-data-groundbased/a1-automatic-weather-stations) |
| Access | STAC API of the Federal Spatial Data Infrastructure: `https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-smn` (and `ch.meteoschweiz.ogd-smn-precip` for precipitation-only stations) |
| Format | CSV, one file per station and granularity |
| Granularity used | Hourly (official MeteoSwiss aggregates, not self-computed) |
| Update frequency | Files split into *historical* (yearly update), *recent* (daily update) and *now* (frequent update) |
| Stations | Candidates: Luzern (LUZ), Egolzwil (EGO), plus a precipitation station if coverage requires it **(to verify)** |
| Volume | Small: a few stations × hourly values |
| Licence | Free use; **source must be cited ("Source: MeteoSwiss")** |

### Parameters (planned)

Hourly precipitation sum, air temperature (mean/min), maximum wind gust, and possibly
relative humidity. Exact parameter codes will be taken from the MeteoSwiss parameter
metadata **(to verify)**.

### Data-quality risks

- **Snow:** automatic snow-depth data is not manually checked and is not an official series; snow is therefore derived from precipitation and temperature.
- **Representativeness:** a few stations cannot capture local conditions at every stop (e.g. valleys vs. lake area).
- **Missing values / outages:** individual hours may be missing and must be handled explicitly.
- **Revisions:** recent data may be corrected later; ingestion must be rerunnable so that corrected values replace old ones.
- **Time zone:** MeteoSwiss timestamps are expected to be UTC **(to verify)**; conversion to Swiss local time is required for joining.
