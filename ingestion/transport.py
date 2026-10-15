"""Load one operating day of Ist-Daten into raw.stop_events.

    python -m ingestion.transport --date 2026-10-08

1. Test the database connection and read our 51 stop numbers from raw.stops.
2. Find and download the day's file into a temporary folder (deleted afterwards).
3. Keep the rail rows at our stops, every column unchanged (D6), and check they belong to that day.
4. Replace that day in one transaction (D10): lock the table, delete the day, insert, compare the
   committed count with the filtered count. Any error rolls back and the previous version stays,
   so a rerun never creates duplicates.
"""
import sys
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
from sqlalchemy import text

from ingestion.cli import operating_day_argument
from ingestion.db import check_connection, ensure_schema, get_engine
from ingestion.sources import SourceNotAvailable, download, find_daily_link, read_rail_rows


def our_stop_numbers(engine) -> set[str]:
    with engine.begin() as connection:
        ensure_schema(connection)
        numbers = set(connection.scalars(text("SELECT number FROM raw.stops")))
    if not numbers:
        raise SystemExit("raw.stops is empty: load the stop list first (python -m ingestion.stops).")
    return numbers


def prepare_rows(rows: pd.DataFrame, day: date, source_file: str) -> pd.DataFrame:
    """Check the rows belong to the requested day, then add the load columns."""
    if rows.empty:
        raise ValueError(f"The file has no rail rows at our stops for {day}: wrong file or changed filter values.")
    days_in_file = set(rows["BETRIEBSTAG"].unique())
    if days_in_file != {day.strftime("%d.%m.%Y")}:
        raise ValueError(f"Expected operating day {day:%d.%m.%Y} only, the file contains {sorted(days_in_file)}.")
    duplicates = rows.duplicated(["FAHRT_BEZEICHNER", "BPUIC"]).sum()
    if duplicates:
        raise ValueError(f"{duplicates} rows share a journey and stop: the table key (D10) would be violated.")

    prepared = rows.rename(columns=str.lower)
    prepared.insert(0, "operating_day", day)
    prepared["source_file"] = source_file
    return prepared


def load_day(engine, day: date, rows: pd.DataFrame) -> int:
    """Replace one operating day in raw.stop_events inside one transaction."""
    with engine.begin() as connection:
        connection.execute(text("SET LOCAL lock_timeout = '10s'"))
        ensure_schema(connection)
        # Two runs for the same day can't replace it at the same time
        connection.execute(text("LOCK TABLE raw.stop_events IN SHARE ROW EXCLUSIVE MODE"))
        deleted = connection.execute(
            text("DELETE FROM raw.stop_events WHERE operating_day = :day"), {"day": day}
        ).rowcount
        rows.to_sql("stop_events", connection, schema="raw", if_exists="append",
                    index=False, chunksize=1_000, method="multi")
        committed = connection.scalar(
            text("SELECT COUNT(*) FROM raw.stop_events WHERE operating_day = :day"), {"day": day}
        )
        if committed != len(rows):
            raise ValueError(f"{committed} rows in the table but {len(rows)} filtered; rolling back {day}.")
    return deleted


def main() -> None:
    day = operating_day_argument(__doc__)
    engine = get_engine()
    try:
        check_connection(engine)
        stop_numbers = our_stop_numbers(engine)
        url = find_daily_link(day.isoformat())

        with TemporaryDirectory() as folder:
            path = download(url, Path(folder) / f"{day.isoformat()}_istdaten.csv")
            rows, total = read_rail_rows(path, stop_numbers)

        prepared = prepare_rows(rows, day, source_file=url.rsplit("/", 1)[-1])
        replaced = load_day(engine, day, prepared)
        print(f"{day}: {total:,} rows in file, {len(prepared):,} rail rows at our stops "
              f"({prepared['bpuic'].nunique()} of {len(stop_numbers)} stops)")
        print(f"{day}: committed {len(prepared):,} rows to raw.stop_events "
              f"(replaced {replaced:,} rows of an earlier load)")
    except SourceNotAvailable as problem:
        print(f"{day}: {problem}", file=sys.stderr)
        sys.exit(1)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()