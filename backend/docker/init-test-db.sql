-- Runs once, on first start of an empty volume (after the image's own PostGIS setup).
-- 1) Separate database for the test suite (real PostGIS, never the dev data).
-- 2) The postgis image also installs the US "tiger" geocoder and topology, which add unrelated
--    tables (including one called "place") and change search_path. We don't use them: remove them
--    so our schema is the only one in play.
CREATE DATABASE pinpoint_test;

\connect pinpoint
CREATE EXTENSION IF NOT EXISTS postgis;
DROP EXTENSION IF EXISTS postgis_tiger_geocoder CASCADE;
DROP EXTENSION IF EXISTS postgis_topology CASCADE;
DROP EXTENSION IF EXISTS fuzzystrmatch CASCADE;
ALTER DATABASE pinpoint RESET search_path;

\connect pinpoint_test
CREATE EXTENSION IF NOT EXISTS postgis;
