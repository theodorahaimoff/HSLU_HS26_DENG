"""Create or update the transformation views (transformations/*.sql, in file-name order).

    python -m ingestion.transform

Each file uses CREATE OR REPLACE, so running this again is safe. All files run in one transaction:
if one fails, none of the views change. Afterwards the script checks that staging has exactly as
many rows as raw (rows are flagged, never removed, D7).
"""
from sqlalchemy import text

from ingestion.db import REPO, check_connection, ensure_schema, get_engine

TRANSFORMATIONS = REPO / "transformations"


def main() -> None:
    files = sorted(TRANSFORMATIONS.glob("*.sql"))
    if not files:
        raise SystemExit(f"No .sql files in {TRANSFORMATIONS}.")
    engine = get_engine()
    try:
        check_connection(engine)
        with engine.begin() as connection:
            ensure_schema(connection)
            for path in files:
                connection.execute(text(path.read_text(encoding="utf-8")))
                print(f"applied {path.name}")
            raw = connection.scalar(text("SELECT COUNT(*) FROM raw.stop_events"))
            staged = connection.scalar(text("SELECT COUNT(*) FROM staging.stop_events"))
            if staged != raw:
                raise ValueError(f"staging.stop_events has {staged} rows but raw has {raw}; rolling back.")
        print(f"staging.stop_events: {staged:,} rows, the same as raw.stop_events")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()