-- 009: benchmarks.section — which result section a benchmark reads.
-- The BBS-1 catalog JSONs carry "section" per record (blast/uniprot/msa/...);
-- migration 008 omitted the column, so every non-blast benchmark defaulted to
-- the runner's "blast" fallback and read the wrong part of the result.

alter table benchmarks add column if not exists section text not null default 'blast';

comment on column benchmarks.section is
  'Result context section the benchmark evaluates (blast, uniprot, msa, phylo, docking, md, ngs, ...).';