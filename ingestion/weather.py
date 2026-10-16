"""Load one operating day of hourly SwissMetNet weather into raw.weather_hourly.

    python -m ingestion.weather --date 2026-10-08

1. Test the database connection and read the weather stations from raw.stops.
2. For each station, find and download the "recent" hourly file (1 January to yesterday).
3. Keep the hours of that Swiss calendar day and the 7 parameters we need, values unchanged.
4. Replace that day in one transaction, like ingestion/transport.py. A rerun never creates
   duplicates, and values that MeteoSwiss corrected replace the old ones.
"""
import io
import sys
from datetime import date, timedelta

import pandas as pd
import requests
from sqlalchemy import text

from ingestion.cli import operating_day_argument
from ingestion.db import check_connection, ensure_schema, get_engine
from ingestion.sources import SourceNotAvailable

STAC_ITEMS = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-smn/items/"
LOCAL_TZ = "Europe/Zurich"
PARAMETERS = ["rre150h0", "tre200h0", "tre200hn", "tre200hx", "tre005hn", "fu3010h1", "htoauths"]


def weather_stations(engine) -> list[str]:
    with engine.begin() as connection:
        ensure_schema(connection)
        stations = list(connection.scalars(text("SELECT DISTINCT weather_station FROM raw.stops ORDER BY 1")))
    if not stations:
        raise SystemExit("raw.stops is empty: load the stop list first (python -m ingestion.stops).")
    return stations


def find_recent_link(station: str) -> str:
    """Download URL of the station's hourly 'recent' file, read from the STAC API."""
    response = requests.get(STAC_ITEMS + station.lower(), timeout=60)
    response.raise_for_status()
    links = [asset["href"] for key, asset in response.json()["assets"].items() if "_h_recent" in key]
    if not links:
        raise SourceNotAvailable(f"No hourly 'recent' file for station {station} in the STAC API.")
    return links[0]


def hours_in_day(day: date) -> int:
    """24 hours, or 23 / 25 on the days the clocks change."""
    start = pd.Timestamp(day.isoformat(), tz=LOCAL_TZ)
    end = pd.Timestamp((day + timedelta(days=1)).isoformat(), tz=LOCAL_TZ)
    return int((end - start) / pd.Timedelta(hours=1))


def read_station_day(station: str, day: date) -> pd.DataFrame:
    """The hours of one Swiss calendar day for one station."""
    url = find_recent_link(station)
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    file = pd.read_csv(io.BytesIO(response.content), sep=";", encoding="cp1252")

    # A changed file fails loudly. An empty column is fine: not every station measures everything.
    missing = [name for name in ["station_abbr", "reference_timestamp", *PARAMETERS] if name not in file.columns]
    if missing:
        raise ValueError(f"{station}: columns missing in {url}: {missing}")
    if set(file["station_abbr"]) != {station}:
        raise ValueError(f"{station}: the file contains stations {sorted(set(file['station_abbr']))}")

    # Timestamps are UTC and mark the END of the hour, so an hour belongs to the day it started in.
    observed_at = pd.to_datetime(file["reference_timestamp"], format="%d.%m.%Y %H:%M", utc=True)
    local_day = (observed_at - pd.Timedelta(hours=1)).dt.tz_convert(LOCAL_TZ).dt.date

    rows = pd.DataFrame({"station": station, "observed_at": observed_at, "operating_day": local_day})
    for name in PARAMETERS:
        rows[name] = pd.to_numeric(file[name], errors="raise")
    rows["source_file"] = url.rsplit("/", 1)[-1]
    rows = rows[rows["operating_day"] == day]

    expected = hours_in_day(day)
    if len(rows) != expected:
        raise SourceNotAvailable(
            f"{station}: {len(rows)} of {expected} hours for {day} in {url}. "
            "The recent file starts on 1 January and is updated daily: try again later."
        )
    if rows.duplicated(["station", "observed_at"]).any():
        raise ValueError(f"{station}: two rows for the same hour, the table key would be violated.")
    return rows


def load_day(engine, day: date, rows: pd.DataFrame) -> int:
    """Replace one operating day in raw.weather_hourly inside one transaction."""
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '10s'"))
        ensure_schema(connection)
        # Two runs for the same day can't replace it at the same time
        connection.execute(text("LOCK TABLE raw.weather_hourly IN SHARE ROW EXCLUSIVE MODE"))
        deleted = connection.execute(
            text("DELETE FROM raw.weather_hourly WHERE operating_day = :day"), {"day": day}
        ).rowcount
        rows.to_sql("weather_hourly", connection, schema="raw", if_exists="append",
                    index=False, chunksize=1_000, method="multi")
        committed = connection.scalar(
            text("SELECT COUNT(*) FROM raw.weather_hourly WHERE operating_day = :day"), {"day": day}
        )
        if committed != len(rows):
            raise ValueError(f"{committed} rows in the table but {len(rows)} loaded; rolling back {day}.")
    return deleted


def main() -> None:
    day = operating_day_argument(__doc__)
    engine = get_engine()
    try:
        check_connection(engine)
        stations = weather_stations(engine)
        rows = pd.concat([read_station_day(station, day) for station in stations], ignore_index=True)
        replaced = load_day(engine, day, rows)
        print(f"{day}: {len(rows)} hourly rows for {len(stations)} stations ({', '.join(stations)})")
        print(f"{day}: committed {len(rows)} rows to raw.weather_hourly "
              f"(replaced {replaced} rows of an earlier load)")
    except SourceNotAvailable as problem:
        print(f"{day}: {problem}", file=sys.stderr)
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
