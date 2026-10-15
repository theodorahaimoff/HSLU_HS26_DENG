-- Staging: one row per stop event, typed, flagged and with delays in minutes.
-- Grain: one journey at one stop on one operating day, the same rows as raw.stop_events (D7, D10).
-- Nothing is removed: rows without a measured time or of cancelled trains stay, with a status,
-- and their delay is NULL. Whether a delay counts as "delayed" (threshold) is decided later,
-- in the curated tables, so it can change without touching this view.
-- Times are Swiss local time as published by Ist-Daten (column names end in _local).

CREATE SCHEMA IF NOT EXISTS staging;

CREATE OR REPLACE VIEW staging.stop_events AS
WITH typed AS (
    SELECT
        e.operating_day,
        e.fahrt_bezeichner                                       AS journey_id,
        e.bpuic                                                  AS stop_number,
        s.name                                                   AS stop_name,
        s.weather_station,
        e.betreiber_abk                                          AS operator,
        e.linien_text                                            AS line,
        e.verkehrsmittel_text                                    AS train_category,
        e.faellt_aus_tf = 'true'                                 AS is_cancelled,
        e.zusatzfahrt_tf = 'true'                                AS is_extra_trip,
        e.an_prognose_status,
        e.ab_prognose_status,
        e.ankunftszeit IS NOT NULL                               AS has_scheduled_arrival,
        e.abfahrtszeit IS NOT NULL                               AS has_scheduled_departure,
        to_timestamp(e.ankunftszeit, 'DD.MM.YYYY HH24:MI')::timestamp     AS arrival_scheduled_local,
        to_timestamp(e.an_prognose,  'DD.MM.YYYY HH24:MI:SS')::timestamp  AS arrival_actual_local,
        to_timestamp(e.abfahrtszeit, 'DD.MM.YYYY HH24:MI')::timestamp     AS departure_scheduled_local,
        to_timestamp(e.ab_prognose,  'DD.MM.YYYY HH24:MI:SS')::timestamp  AS departure_actual_local
    FROM raw.stop_events AS e
    -- LEFT JOIN: a stop missing from raw.stops would keep its rows (with NULL names), not vanish;
    -- validate.py fails the run in that case
    LEFT JOIN raw.stops AS s ON s.number = e.bpuic
)
SELECT
    operating_day,
    journey_id,
    stop_number,
    stop_name,
    weather_station,
    operator,
    line,
    train_category,
    is_cancelled,
    is_extra_trip,

    -- Stop role (D2): no scheduled arrival = the journey starts here, no scheduled departure = it ends here
    CASE
        WHEN NOT has_scheduled_arrival THEN 'origin'
        WHEN NOT has_scheduled_departure THEN 'terminus'
        ELSE 'intermediate'
    END AS stop_role,

    arrival_scheduled_local,
    arrival_actual_local,
    departure_scheduled_local,
    departure_actual_local,

    -- What the actual time is based on (D7). UNBEKANNT = cancelled train (exploration, 8 Oct)
    CASE
        WHEN NOT has_scheduled_arrival THEN 'no scheduled time'
        WHEN an_prognose_status = 'REAL' THEN 'measured'
        WHEN an_prognose_status = 'PROGNOSE' THEN 'forecast only'
        WHEN an_prognose_status = 'UNBEKANNT' THEN 'unknown'
        ELSE 'unexpected value'
    END AS arrival_basis,
    CASE
        WHEN NOT has_scheduled_departure THEN 'no scheduled time'
        WHEN ab_prognose_status = 'REAL' THEN 'measured'
        WHEN ab_prognose_status = 'PROGNOSE' THEN 'forecast only'
        WHEN ab_prognose_status = 'UNBEKANNT' THEN 'unknown'
        ELSE 'unexpected value'
    END AS departure_basis,

    -- Delays only from measured times of trains that ran; NULL otherwise. Negative = early.
    CASE
        WHEN an_prognose_status = 'REAL' AND NOT is_cancelled
        THEN round((extract(epoch FROM arrival_actual_local - arrival_scheduled_local) / 60)::numeric, 2)
    END AS arrival_delay_min,
    CASE
        WHEN ab_prognose_status = 'REAL' AND NOT is_cancelled
        THEN round((extract(epoch FROM departure_actual_local - departure_scheduled_local) / 60)::numeric, 2)
    END AS departure_delay_min
FROM typed;