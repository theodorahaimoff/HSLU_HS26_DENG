"""Check one loaded operating day. A green load only proves the database accepted the rows (D8).

    python -m ingestion.validate --date 2026-10-08

Runs every check, prints each result, and exits with an error if any check fails, so the Kestra
execution fails instead of only printing a warning. Checks for the weather table are added
together with ingestion/weather.py.
"""
import sys

from sqlalchemy import text

from ingestion.cli import operating_day_argument
from ingestion.db import check_connection, get_engine
from ingestion.stops import EXPECTED_STOPS

KNOWN_STATUS = ("REAL", "PROGNOSE", "UNBEKANNT")     # UNBEKANNT = cancelled train (exploration, 8 Oct)
FLAGS = ("faellt_aus_tf", "zusatzfahrt_tf", "durchfahrt_tf")

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