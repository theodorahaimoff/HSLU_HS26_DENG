"""Load the stop list and each stop's weather station into raw.stops (full snapshot).

    python -m ingestion.stops

1. Find the current file on the dataset page, download it and keep the rail stops in canton LU (filters in code, D3).
2. Fail unless exactly 51 stops remain, so a change in the source is noticed, not silently loaded.
3. Give each stop the nearest SwissMetNet station within 300 m altitude difference (D4).
4. Replace the whole table in one transaction: a failure leaves the previous stop list in place.
"""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from sqlalchemy import text

from ingestion.db import check_connection, ensure_schema, get_engine
from ingestion.sources import SMN_STATIONS_URL, SourceNotAvailable, download, find_service_points_link

EXPECTED_STOPS = 51
MAX_HEIGHT_DIFF_M = 300


def select_stops(service_points: pd.DataFrame) -> pd.DataFrame:
    """The four documented filters. Booleans are the strings true/false; meansOfTransport can be 'BUS|TRAIN'."""
    is_true = lambda column: service_points[column].str.lower() == "true"
    selected = service_points[
        (service_points["cantonAbbreviation"] == "LU")
        & is_true("stopPoint")
        & is_true("hasGeolocation")
        & service_points["meansOfTransport"].str.contains("TRAIN", na=False)
    ]
    return selected.copy()


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance in km between points given in degrees (works on numpy arrays)."""
    lat1, lon1, lat2, lon2 = map(np.radians, (lat1, lon1, lat2, lon2))
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371 * np.arcsin(np.sqrt(a))


def map_weather_stations(stops: pd.DataFrame, stations: pd.DataFrame) -> pd.DataFrame:
    """Nearest station per stop, skipping stations more than MAX_HEIGHT_DIFF_M higher or lower."""
    stop_lat = stops["wgs84North"].astype(float).to_numpy()[:, None]
    stop_lon = stops["wgs84East"].astype(float).to_numpy()[:, None]
    stop_h = stops["height"].astype(float).to_numpy()[:, None]
    stn_lat = stations["station_coordinates_wgs84_lat"].astype(float).to_numpy()[None, :]
    stn_lon = stations["station_coordinates_wgs84_lon"].astype(float).to_numpy()[None, :]
    stn_h = stations["station_height_masl"].astype(float).to_numpy()[None, :]

    dist = haversine_km(stop_lat, stop_lon, stn_lat, stn_lon)
    height_diff = np.abs(stop_h - stn_h)
    allowed = np.where(height_diff <= MAX_HEIGHT_DIFF_M, dist, np.inf)
    if np.isinf(allowed.min(axis=1)).any():
        raise ValueError(f"A stop has no weather station within {MAX_HEIGHT_DIFF_M} m altitude difference.")
    best = allowed.argmin(axis=1)
    rows = np.arange(len(stops))

    return pd.DataFrame({
        "number": stops["number"].to_numpy(),
        "sloid": stops["sloid"].to_numpy(),
        "name": stops["designationOfficial"].to_numpy(),
        "canton": stops["cantonAbbreviation"].to_numpy(),
        "wgs84_lat": stop_lat[:, 0],
        "wgs84_lon": stop_lon[:, 0],
        "height_m": stop_h[:, 0],
        "weather_station": stations["station_abbr"].to_numpy()[best],
        "station_distance_km": dist[rows, best].round(2),
        "station_height_diff_m": height_diff[rows, best].round(1),
    })


def load_stops(engine, table: pd.DataFrame) -> None:
    """Replace raw.stops in one transaction and check the committed count."""
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '10s'"))
        ensure_schema(connection)
        connection.execute(text("LOCK TABLE raw.stops IN SHARE ROW EXCLUSIVE MODE"))
        connection.execute(text("DELETE FROM raw.stops"))
        table.to_sql("stops", connection, schema="raw", if_exists="append", index=False, method="multi")
        loaded = connection.scalar(text("SELECT COUNT(*) FROM raw.stops"))
        if loaded != len(table):
            raise ValueError(f"Loaded {loaded} stops but expected {len(table)}; rolling back.")


def main() -> None:
    engine = get_engine()
    try:
        check_connection(engine)
        with TemporaryDirectory() as folder:
            sp_path = download(find_service_points_link(), Path(folder) / "service_points.csv")
            smn_path = download(SMN_STATIONS_URL, Path(folder) / "smn_stations.csv")
            service_points = pd.read_csv(sp_path, sep=";", dtype=str, encoding="utf-8-sig")
            stations = pd.read_csv(smn_path, sep=";", encoding="cp1252")   # MeteoSwiss uses Windows-1252

        stops = select_stops(service_points)
        print(f"service points: {len(service_points):,}   stops after filters: {len(stops)}")
        if len(stops) != EXPECTED_STOPS or stops["number"].nunique() != len(stops):
            raise SystemExit(
                f"Expected {EXPECTED_STOPS} unique stops, got {len(stops)} "
                f"({stops['number'].nunique()} unique). The service points changed: check before loading."
            )

        table = map_weather_stations(stops, stations)
        load_stops(engine, table)
        print(f"committed {len(table)} stops to raw.stops")
        print("stops per weather station:", table["weather_station"].value_counts().sort_index().to_dict())
        print(f"largest stop-to-station distance: {table['station_distance_km'].max():.1f} km")
    except SourceNotAvailable as problem:
        print(problem, file=sys.stderr)
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()