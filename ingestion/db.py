"""Database connection shared by all ingestion scripts.

Settings come from environment variables. In Kestra the flow sets them; on your own machine they
are read from the repository's .env file (variables that are already set are not overwritten).
"""
import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, Engine, create_engine, text

REPO = Path(__file__).resolve().parent.parent
SCHEMA_SQL = REPO / "sql" / "schema.sql"


def _setting(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing setting {name}: copy .env.example to .env and fill it in.")
    return value


def get_engine() -> Engine:
    """Engine for our PostgreSQL database. Fails fast with a clear message if a setting is missing."""
    load_dotenv(REPO / ".env")
    url = URL.create(
        "postgresql+psycopg2",
        host=_setting("POSTGRES_HOST"),
        port=int(os.environ.get("POSTGRES_PORT", "5432")),
        database=_setting("POSTGRES_DB"),
        username=_setting("POSTGRES_USER"),
        password=_setting("POSTGRES_PASSWORD"),
    )
    return create_engine(url, connect_args={"connect_timeout": 10}, hide_parameters=True)


def check_connection(engine: Engine) -> None:
    """Test the connection before downloading anything large (course pattern, ingest_months.py)."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))


def ensure_schema(connection) -> None:
    """Create the raw schema and tables if they don't exist yet (sql/schema.sql)."""
    connection.execute(text(SCHEMA_SQL.read_text(encoding="utf-8")))