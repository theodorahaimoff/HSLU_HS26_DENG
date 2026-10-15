"""Command-line helpers shared by the scripts that work on one operating day."""
import argparse
from datetime import date


def operating_day_argument(description: str) -> date:
    """Parse --date YYYY-MM-DD. Kestra passes the day; scripts never use the machine's date (D11)."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--date", required=True, type=date.fromisoformat,
                        help="operating day to process, e.g. 2026-10-08")
    return parser.parse_args().date