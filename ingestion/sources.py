"""Where the source files are and how to read them. Shared by the ingestion scripts."""
import re
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests

DATASET_PAGE = "https://data.opentransportdata.swiss/dataset/ist-daten-v2"
# Service points: the file gets a new resource ID when it is republished, so a fixed download URL
# breaks (the URL from 11 Oct returned 404 on 15 Oct). The link is read from the dataset page instead.
SERVICE_POINTS_PAGE = "https://data.opentransportdata.swiss/dataset/service-point-v2"
SERVICE_POINTS_FILE = "actual-date-swiss-service-point.csv"
SMN_STATIONS_URL = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/ogd-smn_meta_stations.csv"

# The 22 columns of an Ist-Daten v2 file. A file with different columns is rejected (schema change).
IST_COLUMNS = [
    "BETRIEBSTAG", "FAHRT_BEZEICHNER", "BETREIBER_ID", "BETREIBER_ABK", "BETREIBER_NAME",
    "PRODUKT_ID", "LINIEN_ID", "LINIEN_TEXT", "UMLAUF_ID", "VERKEHRSMITTEL_TEXT",
    "ZUSATZFAHRT_TF", "FAELLT_AUS_TF", "BPUIC", "HALTESTELLEN_NAME", "ANKUNFTSZEIT",
    "AN_PROGNOSE", "AN_PROGNOSE_STATUS", "ABFAHRTSZEIT", "AB_PROGNOSE", "AB_PROGNOSE_STATUS",
    "DURCHFAHRT_TF", "SLOID",
]


class SourceNotAvailable(Exception):
    """The requested file is not (yet) published. Usually temporary, so Kestra retries."""


def find_service_points_link() -> str:
    """Current download URL of the service points file, read from its dataset page."""
    page = requests.get(SERVICE_POINTS_PAGE, timeout=60)
    page.raise_for_status()
    pattern = r'href="([^"]*/download/' + re.escape(SERVICE_POINTS_FILE) + r')"'
    links = re.findall(pattern, page.text, flags=re.I)
    if not links:
        raise SourceNotAvailable(
            f"No link to {SERVICE_POINTS_FILE} on {SERVICE_POINTS_PAGE}: the page layout or file name "
            "may have changed. Check the page in a browser."
        )
    return urljoin(SERVICE_POINTS_PAGE, links[0])


def find_daily_link(day: str) -> str:
    """Download URL of the Ist-Daten file for one operating day (YYYY-MM-DD).

    Each daily file has its own resource ID, so the URL can't be built from the date. The link is
    read from the dataset page, which lists the last 50 days (rolling window).
    """
    page = requests.get(DATASET_PAGE, timeout=60)
    page.raise_for_status()
    links = re.findall(rf'href="([^"]*/download/{day}_istdaten\.csv)"', page.text, flags=re.I)
    if not links:
        listed = sorted(set(re.findall(r"/download/(\d{4}-\d{2}-\d{2})_istdaten\.csv", page.text, flags=re.I)))
        if not listed:
            raise SourceNotAvailable(
                "The dataset page lists no daily files at all: the page layout may have changed. "
                f"Check {DATASET_PAGE} in a browser."
            )
        raise SourceNotAvailable(
            f"No file for {day} on the dataset page. Listed: {listed[0]} to {listed[-1]}. "
            "A day not published yet usually appears by about 05:15 the next morning; "
            "days older than the window are in the monthly archive."
        )
    return urljoin(DATASET_PAGE, links[0])


def download(url: str, target: Path) -> Path:
    """Stream a file to disk in 1 MB pieces, so a 660 MB file never has to fit in memory."""
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(target, "wb") as output:
            for piece in response.iter_content(chunk_size=1 << 20):
                output.write(piece)
    print(f"downloaded {target.name}: {target.stat().st_size / 1e6:.1f} MB", flush=True)
    return target


def read_rail_rows(source, stop_numbers: set[str]) -> tuple[pd.DataFrame, int]:
    """Read an Ist-Daten file in chunks and keep the rail rows at our stops, every column unchanged.

    `source` is a path or an open file (e.g. a file inside an archive ZIP). Returns the kept rows and
    the number of rows in the whole file. PRODUKT_ID is compared case-insensitively (D6).
    """
    kept, total = [], 0
    for chunk in pd.read_csv(source, sep=";", dtype=str, encoding="utf-8-sig", chunksize=200_000):
        if total == 0 and list(chunk.columns) != IST_COLUMNS:
            missing = sorted(set(IST_COLUMNS) - set(chunk.columns))
            extra = sorted(set(chunk.columns) - set(IST_COLUMNS))
            raise ValueError(
                f"Ist-Daten columns changed (missing: {missing}, new: {extra}). "
                "Update sql/schema.sql and IST_COLUMNS before loading."
            )
        total += len(chunk)
        is_rail = chunk["PRODUKT_ID"].str.lower() == "zug"
        kept.append(chunk[is_rail & chunk["BPUIC"].isin(stop_numbers)])
    rows = pd.concat(kept, ignore_index=True) if kept else pd.DataFrame(columns=IST_COLUMNS)
    return rows, total