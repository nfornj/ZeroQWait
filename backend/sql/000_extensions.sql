-- Bootstrap: enable pgvector before any application tables are created.
-- This file is mounted into /docker-entrypoint-initdb.d/ in docker-compose so
-- Postgres runs it automatically on first initialisation of a fresh volume.
CREATE EXTENSION IF NOT EXISTS vector;
