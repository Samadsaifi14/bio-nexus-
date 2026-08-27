-- 011_pipeline_templates.sql — Saveable pipeline templates
-- Users can save named pipeline configurations with locked parameters
-- and share them via the existing share_token mechanism.

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema = 'public' AND table_name = 'pipeline_templates'
  ) THEN
    CREATE TABLE public.pipeline_templates (
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      user_id uuid REFERENCES public.profiles(id) ON DELETE CASCADE,
      name text NOT NULL,
      description text NOT NULL DEFAULT '',
      steps jsonb NOT NULL DEFAULT '[]'::jsonb,
      parameters jsonb NOT NULL DEFAULT '{}'::jsonb,
      share_token text UNIQUE,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now()
    );
  END IF;
END $$;

ALTER TABLE public.pipeline_templates ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'pipeline_templates' AND policyname = 'Users can view own templates'
  ) THEN
    CREATE POLICY "Users can view own templates"
      ON public.pipeline_templates FOR SELECT
      USING (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'pipeline_templates' AND policyname = 'Users can insert own templates'
  ) THEN
    CREATE POLICY "Users can insert own templates"
      ON public.pipeline_templates FOR INSERT
      WITH CHECK (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'pipeline_templates' AND policyname = 'Users can update own templates'
  ) THEN
    CREATE POLICY "Users can update own templates"
      ON public.pipeline_templates FOR UPDATE
      USING (auth.uid() = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'pipeline_templates' AND policyname = 'Users can delete own templates'
  ) THEN
    CREATE POLICY "Users can delete own templates"
      ON public.pipeline_templates FOR DELETE
      USING (auth.uid() = user_id);
  END IF;

  -- Public read for shared templates (share_token set)
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'pipeline_templates' AND policyname = 'Anyone can view shared templates'
  ) THEN
    CREATE POLICY "Anyone can view shared templates"
      ON public.pipeline_templates FOR SELECT
      USING (share_token IS NOT NULL);
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_pipeline_templates_user ON public.pipeline_templates(user_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_templates_share ON public.pipeline_templates(share_token)
  WHERE share_token IS NOT NULL;
