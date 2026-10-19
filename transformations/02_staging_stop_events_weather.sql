-- Staging: every stop event with the weather of its station in the hour of the train.
-- Grain: one journey at one stop on one operating day, the same rows as staging.stop_events.
--
-- Which time: the SCHEDULED time of the stop event (departure, or arrival at the terminus).
-- It exists for every row, including cancelled trains, which have no actual time. The weather
-- in the hour the train should have been there is the weather that could have caused a delay
-- or a cancellation.
--
-- Which hour: MeteoSwiss timestamps are UTC and mark the END of the hour (ingestion/weather.py).
-- A train at 07:40 Swiss time falls in the hour 07:00-08:00, which MeteoSwiss labels with its
-- end, 08:00 Swiss time = 06:00 UTC in summer. So: start of the local hour, + 1 hour, as UTC.
--
-- LEFT JOIN: (station, hour) is the key of raw.weather_hourly, so each stop event matches at
-- most one weather row and no row is lost or duplicated. Weather is NULL when that hour isn't
-- loaded, e.g. a train after midnight whose calendar day hasn't been loaded yet.

CREATE OR REPLACE VIEW staging.stop_events_weather AS
WITH events AS (
    SELECT
        e.*,
        COALESCE(e.departure_scheduled_local, e.arrival_scheduled_local) AS event_scheduled_local
    FROM staging.stop_events AS e
)
SELECT
    e.*,
    (date_trunc('hour', e.event_scheduled_local) AT TIME ZONE 'Europe/Zurich')
        + interval '1 hour'                        AS weather_hour_end_utc,
    w.rre150h0                                     AS precipitation_mm,
    w.tre200h0                                     AS temperature_c,
    w.tre200hn                                     AS temperature_min_c,
    w.tre200hx                                     AS temperature_max_c,
    w.tre005hn                                     AS grass_temperature_min_c,  -- LUZ only
    w.fu3010h1                                     AS gust_max_kmh,
    w.htoauths                                     AS snow_depth_cm             -- not at EGO, MOA
FROM events AS e
LEFT JOIN raw.weather_hourly AS w
       ON w.station = e.weather_station
      AND w.observed_at = (date_trunc('hour', e.event_scheduled_local) AT TIME ZONE 'Europe/Zurich')
                          + interval '1 hour';