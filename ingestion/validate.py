"""Check one loaded operating day. A green load only proves the database accepted the rows (D8).

    python -m ingestion.validate --date 2026-10-08

Runs every check, prints each result, and exits with an error if any check fails, so the Kestra
execution fails instead of only printing a warning. The weather checks cover raw.weather_hourly.
"""
import sys

from sqlalchemy import text

from ingestion.cli import operating_day_argument
from ingestion.db import check_connection, get_engine
from ingestion.stops import EXPECTED_STOPS

KNOWN_STATUS = ("REAL", "PROGNOSE", "UNBEKANNT")     # UNBEKANNT = cancelled train (exploration, 8 Oct)
FLAGS = ("faellt_aus_tf", "zusatzfahrt_tf", "durchfahrt_tf")

# Hours of the Swiss calendar day: 24, or 23 / 25 when the clocks change
HOURS_IN_DAY = (
    "(EXTRACT(EPOCH FROM (CAST(CAST(:day AS date) + 1 AS timestamp) AT TIME ZONE 'Europe/Zurich')"
    " - (CAST(CAST(:day AS date) AS timestamp) AT TIME ZONE 'Europe/Zurich')) / 3600)"
)
# Parameters every station measures. tre005hn and htoauths are missing at some stations, so not here.
CORE_WEATHER = ("rre150h0", "tre200h0", "tre200hn", "tre200hx", "fu3010h1")

CHECKS = [
    ("the stop list has the expected number of stops, each with a weather station",
     "SELECT COUNT(*) FROM raw.stops WHERE weather_station IS NOT NULL",
     lambda n: n == EXPECTED_STOPS),
    ("the day has rows",
     "SELECT COUNT(*) FROM raw.stop_events WHERE operating_day = :day",
     lambda n: n > 0),
    ("every row belongs to one of our stops",
     "SELECT COUNT(*) FROM raw.stop_events e LEFT JOIN raw.stops s ON s.number = e.bpuic "
     "WHERE e.operating_day = :day AND s.number IS NULL",
     lambda n: n == 0),
    ("every row is rail",
     "SELECT COUNT(*) FROM raw.stop_events WHERE operating_day = :day AND lower(produkt_id) <> 'zug'",
     lambda n: n == 0),
    ("arrival and departure status only hold known values",
     "SELECT COUNT(*) FROM raw.stop_events WHERE operating_day = :day AND ("
     f"an_prognose_status NOT IN {KNOWN_STATUS} OR ab_prognose_status NOT IN {KNOWN_STATUS})",
     lambda n: n == 0),
    ("flags only hold true or false",
     "SELECT COUNT(*) FROM raw.stop_events WHERE operating_day = :day AND ("
     + " OR ".join(f"{flag} NOT IN ('true', 'false')" for flag in FLAGS) + ")",
     lambda n: n == 0),
    ("every row has a scheduled arrival or departure",
     "SELECT COUNT(*) FROM raw.stop_events WHERE operating_day = :day "
     "AND ankunftszeit IS NULL AND abfahrtszeit IS NULL",
     lambda n: n == 0),

    # --- weather ---
    ("every weather station of our stops has all hours of the day",
     "SELECT COUNT(*) FROM (SELECT DISTINCT weather_station FROM raw.stops) s "
     "LEFT JOIN (SELECT station, COUNT(*) AS hours FROM raw.weather_hourly "
     "WHERE operating_day = :day GROUP BY station) w ON w.station = s.weather_station "
     f"WHERE COALESCE(w.hours, 0) <> {HOURS_IN_DAY}",
     lambda n: n == 0),
    ("every weather row belongs to a station of our stops",
     "SELECT COUNT(*) FROM raw.weather_hourly w "
     "WHERE w.operating_day = :day AND w.station NOT IN (SELECT weather_station FROM raw.stops)",
     lambda n: n == 0),
    ("every station has a value for each core parameter on the day",
     "SELECT COUNT(*) FROM (SELECT station FROM raw.weather_hourly WHERE operating_day = :day "
     "GROUP BY station HAVING " + " OR ".join(f"COUNT({name}) = 0" for name in CORE_WEATHER) + ") x",
     lambda n: n == 0),
    ("weather values are in a plausible range",
     "SELECT COUNT(*) FROM raw.weather_hourly WHERE operating_day = :day AND ("
     "rre150h0 NOT BETWEEN 0 AND 200 OR fu3010h1 NOT BETWEEN 0 AND 300 "
     "OR tre200h0 NOT BETWEEN -45 AND 45 OR tre200hn NOT BETWEEN -45 AND 45 "
     "OR tre200hx NOT BETWEEN -45 AND 45 OR tre005hn NOT BETWEEN -50 AND 50)",
     lambda n: n == 0),
    ("hourly minimum temperature is not above the maximum",
     "SELECT COUNT(*) FROM raw.weather_hourly WHERE operating_day = :day AND tre200hn > tre200hx",
     lambda n: n == 0),
]


def main() -> None:
    day = operating_day_argument(__doc__)
    engine = get_engine()
    failed = 0
    try:
        check_connection(engine)
        with engine.connect() as connection:
            for description, query, passes in CHECKS:
                value = connection.scalar(text(query), {"day": day})
                ok = passes(value)
                failed += not ok
                print(f"{'PASS' if ok else 'FAIL'}  {description}  (value: {value})")
    finally:
        engine.dispose()

    if failed:
        print(f"{day}: {failed} of {len(CHECKS)} checks failed", file=sys.stderr)
        sys.exit(1)
    print(f"{day}: all {len(CHECKS)} checks passed")


if __name__ == "__main__":
    main()