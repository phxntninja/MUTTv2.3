-- =====================================================================
-- MUTT v2.3 - PostgreSQL Initialization Script
-- =====================================================================
-- This script initializes the PostgreSQL database for MUTT.
-- It is designed to run in Docker's entrypoint-initdb.d/
--
-- Execution order (in docker-compose):
--   1. 01-init.sql (this file) - Create database and user
--   2. 02-schema.sql (mutt_schema.sql) - Create tables and functions
--
-- For manual execution:
--   psql -U postgres -f postgres-init.sql
-- =====================================================================

-- Create database if it doesn't exist
-- Note: In Docker, the database is created automatically via POSTGRES_DB
-- This is for reference/manual setup only

-- Create extensions
\c mutt

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE mutt TO mutt_user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO mutt_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO mutt_user;
GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO mutt_user;

-- Alter default privileges for future objects
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO mutt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO mutt_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO mutt_user;

-- Performance tuning (optional, adjust based on your hardware)
-- ALTER SYSTEM SET shared_buffers = '256MB';
-- ALTER SYSTEM SET effective_cache_size = '1GB';
-- ALTER SYSTEM SET work_mem = '16MB';
-- ALTER SYSTEM SET maintenance_work_mem = '64MB';
-- ALTER SYSTEM SET max_connections = '100';

-- Log settings for debugging (optional)
-- ALTER SYSTEM SET log_statement = 'all';
-- ALTER SYSTEM SET log_duration = on;
-- ALTER SYSTEM SET log_line_prefix = '%t [%p]: [%l-1] user=%u,db=%d,app=%a,client=%h ';

-- Reload configuration
-- SELECT pg_reload_conf();

\echo 'PostgreSQL initialization complete'
