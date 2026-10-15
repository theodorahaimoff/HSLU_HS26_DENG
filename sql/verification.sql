-- Verification queries: run them one by one in pgAdmin (Query Tool on the rail_weather database)
-- after the pipeline has loaded at least one day. Each query says what to expect.

-- 1. Rows per operating day.
--    Expect one row per loaded day, about 5,000-5,500 rows on a weekday, all 51 stops.
--    Running the same day again must not change these numbers (the day is replaced, not appended).
SELECT operating_day,
       COUNT(*)              AS stop_events,
       COUNT(DISTINCT bpuic) AS stops,
       MIN(ingested_at)      AS loaded_at
FROM raw.stop_events
GROUP BY operating_day
ORDER BY operating_day;

-- 2. The stop list. Expect 51 stops in total, spread over the stations CHZ, EGO, LUZ, MOA, SPF
--    (on 15 Oct 2026: CHZ 2, EGO 15, LUZ 20, MOA 8, SPF 6) and at most 14 km to the station.
SELECT weather_station,
       COUNT(*)                      AS stops,
       MAX(station_distance_km)      AS max_distance_km,
       MAX(station_height_diff_m)    AS max_height_diff_m
FROM raw.stops
GROUP BY weather_station
ORDER BY weather_station;

-- 3. No duplicate stop events. Expect no rows: (day, journey, stop) is the table key.
SELECT operating_day, fahrt_bezeichner, bpuic, COUNT(*) AS copies
FROM raw.stop_events
GROUP BY operating_day, fahrt_bezeichner, bpuic
HAVING COUNT(*) > 1;

-- 4. Staging keeps every row. Expect the two counts to be equal for every day.
SELECT r.operating_day, r.raw_rows, s.staging_rows, r.raw_rows = s.staging_rows AS equal
FROM (SELECT operating_day, COUNT(*) AS raw_rows FROM raw.stop_events GROUP BY operating_day) AS r
JOIN (SELECT operating_day, COUNT(*) AS staging_rows FROM staging.stop_events GROUP BY operating_day) AS s
  USING (operating_day)
ORDER BY r.operating_day;

-- 5. What the arrival times are based on. Expect 'measured' for most rows, 'unknown' only for
--    cancelled trains, and no 'unexpected value'.
SELECT operating_day, arrival_basis, is_cancelled, COUNT(*) AS stop_events
FROM staging.stop_events
GROUP BY operating_day, arrival_basis, is_cancelled
ORDER BY operating_day, arrival_basis, is_cancelled;

-- 6. Stop roles. Expect mostly 'intermediate'. Luzern (8505000) is mostly origin or terminus.
SELECT stop_role,
       COUNT(*)                                          AS all_stops,
       COUNT(*) FILTER (WHERE stop_number = '8505000')   AS luzern
FROM staging.stop_events
GROUP BY stop_role
ORDER BY stop_role;

-- 7. Delays (measured, trains that ran). Expect a median around 1 minute and a few percent of
--    trains at 3 minutes or more. Departures run a little later than arrivals.
SELECT operating_day,
       COUNT(arrival_delay_min)                                                   AS measured_arrivals,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY arrival_delay_min)             AS median_arrival_delay_min,
       round(100.0 * AVG((arrival_delay_min >= 3)::int), 1)                       AS pct_arrivals_3min_or_more,
       percentile_cont(0.5) WITHIN GROUP (ORDER BY departure_delay_min)           AS median_departure_delay_min,
       round(100.0 * AVG((departure_delay_min >= 3)::int), 1)                     AS pct_departures_3min_or_more
FROM staging.stop_events
GROUP BY operating_day
ORDER BY operating_day;

-- 8. Cancellations per line. Expect a low share on most lines. A line with nearly all trips
--    cancelled on one day is probably a planned closure (on 8 Oct 2026: S9).
SELECT operating_day, line,
       COUNT(*)                                            AS stop_events,
       COUNT(*) FILTER (WHERE is_cancelled)                AS cancelled,
       round(100.0 * AVG(is_cancelled::int), 1)            AS pct_cancelled
FROM staging.stop_events
GROUP BY operating_day, line
HAVING COUNT(*) FILTER (WHERE is_cancelled) > 0
ORDER BY operating_day, pct_cancelled DESC;