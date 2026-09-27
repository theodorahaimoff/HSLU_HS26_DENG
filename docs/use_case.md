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

1. What is the probability of a train arriving late (e.g. > 3 min) for each weather type and severity level, compared with calm/dry conditions?
2. What is the typical delay (median, 90th percentile) under each weather type and severity?
3. At which severity level do cancellation rates increase noticeably?
4. Which stations and lines in the canton are most weather-sensitive?
5. Does the weather effect differ by time of day (e.g. rush hour)?

The delay threshold (e.g. 3 min, the common Swiss punctuality definition) will be fixed
and documented during implementation.

## Weather types and severity

| Weather type | Basis | Derivation |
|---|---|---|
| Rain | Measured hourly precipitation | Direct |
| Wind | Measured gusts | Direct |
| Heat | Measured temperature | Direct |
| Frost | Measured temperature | Direct |
| Snow | Precipitation + temperature around/below 0 °C | Derived (approximation) |
| Thunderstorm | Short intense precipitation + strong gusts | Derived (proxy) |
| Icy conditions | Precipitation + temperature below 0 °C | Derived (proxy) |

Each type is classified into a small number of severity levels (e.g. none / light /
moderate / severe). Thresholds will be based on MeteoSwiss's published danger-level
criteria and documented in the repository.

**Why our own classification:** historical MeteoSwiss warnings are, to our knowledge,
not available as open data. Deriving severity from measured values is reproducible and
transparent.

## Expected data product

| Table (planned) | Grain (one row = …) | Purpose |
|---|---|---|
| `fact_stop_event` | one train stop event (operating day × journey × stop) enriched with the weather of that hour at the nearest station | Detailed analysis |
| `dim_station` | one rail stop in the canton of Lucerne, with its assigned weather station | Filtering / mapping |
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
