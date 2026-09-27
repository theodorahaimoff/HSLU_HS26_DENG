# Use Case Description

## Problem

Weather is widely assumed to affect train punctuality, but there is no easily accessible,
quantified answer for a specific region. This project quantifies how different weather
types and severities relate to train delays and cancellations in the canton of Lucerne.

## Users

**Primary: commuters in the canton of Lucerne.** They want to know how likely their train
is to be late or cancelled under given weather conditions, so they can plan buffer time.

**Secondary: analysts / regional transport planners.** They want to know which lines,
stations and times of day are most sensitive to weather.

## Analytical questions

1. What is the probability of a train being late (e.g. > 3 min) at departure and at arrival, for each weather type and severity level, compared with calm/dry conditions?
2. What is the typical delay (median, 90th percentile) under each weather type and severity?
3. At which severity level do cancellation rates increase noticeably?
4. Which stations and lines in the canton are most weather-sensitive?
5. Does the weather effect differ by time of day (e.g. rush hour)?

The delay threshold (e.g. 3 min, the common Swiss punctuality definition) will be fixed
and documented during implementation.

## Weather types and severity

All weather types are derived from the hourly SwissMetNet values we download. MeteoSwiss's
official warning criteria also use hail size and lightning for thunderstorms; these are
**not** part of the station data, so our thunderstorm type is a proxy based on rain
intensity and gusts only.

| Weather type | Parameters (hourly) | Derivation |
|---|---|---|
| Rain | `rre150h0` precipitation | Direct; rolling 12 h / 24 h totals for the official levels |
| Wind | `fu3010h1` gust peak (km/h) | Direct |
| Heat | `tre200h0`, `tre200hx` air temperature | Direct (aggregated per day) |
| Frost | `tre200hn` air temperature minimum, `tre005hn` temperature 5 cm above grass | Direct |
| Snow | `rre150h0` + `tre200h0` (precipitation at around/below 0 °C); `htoauths` snow depth only as a supporting check | Derived (approximation) |
| Thunderstorm | `rre150h0` rain intensity (mm/h) + `fu3010h1` gusts; no hail or lightning data | Derived (proxy) |
| Icy conditions | `rre150h0` + `tre200h0` / `tre005hn` below 0 °C | Derived (proxy) |

Each type is classified into a small number of severity levels (e.g. none / light /
moderate / severe).

**Why our own classification:** MeteoSwiss's historical weather warnings (danger levels
1–5) are not published as open data; the
[MeteoSwiss open data catalogue](https://opendatadocs.meteoswiss.ch/) covers ground-based
measurements, atmosphere measurements, climate data, radar data and forecast data, but no
warnings (checked September 2026). Severity is therefore derived from the measured hourly values.

**How the scale is anchored:** the thresholds follow the warning criteria MeteoSwiss
publishes for its danger levels. Important for the implementation:

- The official rain and snow thresholds are **totals over 12 to 72 hours** (e.g. level 2
  continuous rain: 50 mm in 12 h or 70 mm in 24 h), so the pipeline computes rolling totals
  from the hourly values before classifying.
- Short intense rain in thunderstorms is defined **per hour** (30–50 mm/h and > 50 mm/h),
  which can be applied to the hourly values directly.
- MeteoSwiss only warns from **level 2** upwards. Everyday conditions below that (e.g. light
  rain) get our own lower categories, documented as such.

The thresholds used and their MeteoSwiss source are documented in the repository, so the
scale stays traceable to the official classification and is reproducible from the measured
data.

Sources:
- [Beschreibung zu den Gefahrenstufen](https://www.meteoswiss.admin.ch/dam/jcr:a5aa1c52-b634-45dd-9757-12004070c8af/beschreibungenzudengefahrenstufen.pdf)
  (MeteoSwiss, May 2021, German): chapter 4 contains the threshold tables for wind, rain
  and snow per danger level
- MeteoSwiss explanation of the danger levels, one page per hazard, with the values in the
  expandable "Additional information" section of each level, e.g.
  [snow](https://www.meteoswiss.admin.ch/weather/hazards/explanation-of-the-danger-levels/snow.html)
  and [thunderstorms](https://www.meteoswiss.admin.ch/weather/hazards/explanation-of-the-danger-levels/thunderstorms.html)
- [How MeteoSwiss prepares severe-weather warnings](https://www.meteoswiss.admin.ch/weather/hazards/how-severe-weather-warnings-are-prepared.html)
  (warning types and warning regions)

## Expected data product

| Table (planned) | Grain (one row = …) | Purpose |
|---|---|---|
| `fact_stop_event` | one train stop event (operating day × journey × stop), with stop role (origin / terminus / intermediate), arrival delay and departure delay (each only from `REAL` actual times), cancellation flag and the weather of that hour at the assigned station | Detailed analysis |
| `dim_station` | one of the 51 rail stops in the canton of Lucerne, with coordinates, its assigned weather station, distance and altitude difference | Filtering / mapping |
| `dim_weather_hour` | one weather station × hour, with measurements and severity levels | Weather context |
| `agg_weather_punctuality` | one weather type × severity level × station × hour-of-day | Answering the user questions directly |

Grains and table design will be refined for the final milestone.

## Dashboard (Streamlit)

The curated tables are presented in a Streamlit dashboard with two views:

- **Findings:** delay and cancellation rates by weather type and severity, compared with the calm/dry baseline; most weather-sensitive stations and lines; number of observations per result.
- **Current risk:** the user selects a station; the dashboard fetches the latest available MeteoSwiss measurement for the assigned weather station, applies the same severity classification as the pipeline, and looks up the historical delay/cancellation probability for those conditions.

The current-risk view is a lookup, not a prediction model: the pipeline itself stays a
batch pipeline, and the dashboard only reads its results plus one current weather value.

## Limitations of the interpretation

- **Correlation, not causation.** Delays have many causes (technical faults, staff shortages, accidents, personal injuries); the data does not contain causes.
- **Baseline comparison.** Results are always reported relative to calm/dry weather to separate weather-related effects from the general delay level.
- **Rare events.** Severe weather occurs rarely; results for high severity levels may be based on few observations and will be reported with counts.
- **Departures vs. arrivals.** Trains starting at their origin (e.g. Luzern, a terminal station) are usually punctual, while arrivals carry the delay built up along the route. Departure and arrival delays are therefore analysed separately and not mixed into one number.