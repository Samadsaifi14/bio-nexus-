-- 009_page_captures.sql — techspec.md §3
-- One row per external source queried during a pipeline run, storing the
-- human-facing page URL plus extracted text sections and figure image URLs,
-- so the final synthesis can cite real pages instead of bare API endpoints.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'page_captures'
  ) THEN
    CREATE TABLE public.page_captures (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      job_id uuid NOT NULL,
      user_id uuid REFERENCES public.profiles(id) ON DELETE CASCADE,
      source text NOT NULL CHECK (source IN (
        'ncbi', 'uniprot', 'alphafold', 'rcsb', 'interpro',
        'reactome', 'wikipathways', 'string'
      )),
      page_url text NOT NULL,
      title text,
      text_sections jsonb NOT NULL DEFAULT '[]'::jsonb,
      figure_urls jsonb NOT NULL DEFAULT '[]'::jsonb,
      fetch_status text NOT NULL DEFAULT 'captured'
        CHECK (fetch_status IN ('captured', 'failed', 'skipped')),
      error_note text,
      fetched_at timestamptz DEFAULT now(),
      created_at timestamptz NOT NULL DEFAULT now()
    );
  END IF;
END $$;

ALTER TABLE public.page_captures ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'page_captures' AND policyname = 'Users can view own page captures'
  ) THEN
    CREATE POLICY "Users can view own page captures"
      ON public.page_captures FOR SELECT
      USING (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'page_captures' AND policyname = 'Users can insert own page captures'
  ) THEN
    CREATE POLICY "Users can insert own page captures"
      ON public.page_captures FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_page_captures_job ON public.page_captures(job_id);
CREATE INDEX IF NOT EXISTS idx_page_captures_user ON public.page_captures(user_id);
