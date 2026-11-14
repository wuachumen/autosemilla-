/*
# Create AutoSemilla experiment ledger tables

Plain-English summary: adds the online database storage for the AutoSemilla search history, mirroring the local ledger the engine already uses. Each candidate tested is one row, and notes store free-form observations.

1. New Tables
- `experiments`: one row per candidate (seed). Holds its parameters, cheap proxy score, validity, promotion state and, when available, the official verifier outcome (`official_verified`, `ranking_value`).
- `notes`: short observations recorded by the engine, deduplicated by a hash key.

2. Indexes
- `experiments(benchmark, official_verified, ranking_value)` to quickly list the best verified candidates per benchmark.

3. Security
- Row level security is enabled on both tables.
- No user accounts are involved, so the app's anon-key client gets full CRUD on both tables (intentionally shared data for a single-tenant research engine).
- Anyone holding the project's anon key can read and modify these rows; this is documented intent, not an oversight.

4. Important notes
- Idempotent: safe to re-run; uses IF NOT EXISTS and DROP POLICY IF EXISTS.
- No existing data is modified or removed.
- `cheap_score` is a proxy and is never the official competition score.
*/

CREATE TABLE IF NOT EXISTS experiments (
  seed_id text PRIMARY KEY,
  seed jsonb NOT NULL,
  benchmark text NOT NULL CHECK (benchmark IN ('invsqrt', 'dqi', 'dfthcsos')),
  strategy text NOT NULL,
  valid boolean NOT NULL,
  cheap_score double precision NOT NULL,
  features jsonb NOT NULL DEFAULT '{}'::jsonb,
  reasons jsonb NOT NULL DEFAULT '[]'::jsonb,
  elapsed_ms double precision NOT NULL,
  promotion text NOT NULL DEFAULT 'candidate' CHECK (promotion IN ('candidate', 'promoted', 'compiled', 'verified', 'rejected')),
  outcome jsonb,
  ranking_value double precision,
  official_verified boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_experiments_verified_ranking
  ON experiments (benchmark, official_verified, ranking_value);

CREATE TABLE IF NOT EXISTS notes (
  note_id text PRIMARY KEY,
  kind text NOT NULL,
  body text NOT NULL,
  source_hash text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE experiments ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes ENABLE ROW LEVEL SECURITY;

GRANT SELECT, INSERT, UPDATE, DELETE ON experiments TO anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE ON notes TO anon, authenticated;

DROP POLICY IF EXISTS "anon_select_experiments" ON experiments;
CREATE POLICY "anon_select_experiments" ON experiments FOR SELECT
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_experiments" ON experiments;
CREATE POLICY "anon_insert_experiments" ON experiments FOR INSERT
  TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_experiments" ON experiments;
CREATE POLICY "anon_update_experiments" ON experiments FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_experiments" ON experiments;
CREATE POLICY "anon_delete_experiments" ON experiments FOR DELETE
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_select_notes" ON notes;
CREATE POLICY "anon_select_notes" ON notes FOR SELECT
  TO anon, authenticated USING (true);

DROP POLICY IF EXISTS "anon_insert_notes" ON notes;
CREATE POLICY "anon_insert_notes" ON notes FOR INSERT
  TO anon, authenticated WITH CHECK (true);

DROP POLICY IF EXISTS "anon_update_notes" ON notes;
CREATE POLICY "anon_update_notes" ON notes FOR UPDATE
  TO anon, authenticated USING (true) WITH CHECK (true);

DROP POLICY IF EXISTS "anon_delete_notes" ON notes;
CREATE POLICY "anon_delete_notes" ON notes FOR DELETE
  TO anon, authenticated USING (true);
