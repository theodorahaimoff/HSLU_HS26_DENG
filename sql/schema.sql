-- Tables for the raw zone. Every ingestion script runs this file before loading, so a fresh
-- database is set up automatically. "IF NOT EXISTS" makes it safe to run again.

CREATE SCHEMA IF NOT EXISTS raw;

-- The 51 rail stops in canton Lucerne (Service Points v2, filters applied in code: D3)
-- and the SwissMetNet station each stop gets its weather from (D4).
-- Reloaded as a full snapshot by ingestion/stops.py.
CREATE TABLE IF NOT EXISTS raw.stops (
    number                 text PRIMARY KEY,          -- service point number = BPUIC in Ist-Daten
    sloid                  text NOT NULL,
    name                   text NOT NULL,
    canton                 text NOT NULL,
    wgs84_lat              double precision NOT NULL,
    wgs84_lon              double precision NOT NULL,
    height_m               double precision NOT NULL,
    weather_station        text NOT NULL,             -- SwissMetNet abbreviation, e.g. LUZ
    station_distance_km    double precision NOT NULL,
    station_height_diff_m  double precision NOT NULL,
    loaded_at              timestamptz NOT NULL DEFAULT now()
);

-- Ist-Daten v2: one row per stop event (one journey at one stop on one operating day),
-- rail only, at our 51 stops. The 22 source columns are kept unchanged as text (D6);
-- typing, flags and delays are computed later in the staging zone (D7).
-- Loaded one operating day at a time by ingestion/transport.py, which replaces the day (D10).
CREATE TABLE IF NOT EXISTS raw.stop_events (
    operating_day        date NOT NULL,               -- parsed from betriebstag
    betriebstag          text NOT NULL,
    fahrt_bezeichner     text NOT NULL,
    betreiber_id         text,
    betreiber_abk        text,
    betreiber_name       text,
    produkt_id           text,
    linien_id            text,
    linien_text          text,
    umlauf_id            text,
    verkehrsmittel_text  text,
    zusatzfahrt_tf       text,
    faellt_aus_tf        text,
    bpuic                text NOT NULL,
    haltestellen_name    text,
    ankunftszeit         text,
    an_prognose          text,
    an_prognose_status   text,
    abfahrtszeit         text,
    ab_prognose          text,
    ab_prognose_status   text,
    durchfahrt_tf        text,
    sloid                text,
    source_file          text NOT NULL,               -- lineage: which file the row came from
    ingested_at          timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (operating_day, fahrt_bezeichner, bpuic)
);