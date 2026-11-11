-- Extensions required by the FlowDesktop schema.
--
--   vector   — pgvector, used by retrieval_chunks.embedding
--   pg_trgm  — trigram indexes for symbol / name search
--
-- This script runs once, when the database is first initialised.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
