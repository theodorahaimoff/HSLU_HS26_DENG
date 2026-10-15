"""Check that the Ist-Daten file for one operating day is published, before anything is downloaded.

    python -m ingestion.check_source --date 2026-10-08

Fails with a clear message if the file isn't listed yet, so Kestra can retry later (D8, D9).
The server refuses HEAD requests (403), so a streamed GET reads only the headers and closes
without downloading the 660 MB body.
"""
import sys

import requests

from ingestion.cli import operating_day_argument
from ingestion.sources import SourceNotAvailable, find_daily_link


def main() -> None:
    day = operating_day_argument(__doc__).isoformat()
    try:
        url = find_daily_link(day)
        with requests.get(url, stream=True, timeout=60) as response:
            response.raise_for_status()
            size_mb = int(response.headers.get("Content-Length", 0)) / 1e6
            print(f"{day}: file is available ({size_mb:.0f} MB, "
                  f"last modified {response.headers.get('Last-Modified')})")
    except SourceNotAvailable as problem:
        print(f"{day}: {problem}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()