-- 010: benchmarks.difficulty + benchmarks.registry_version (Component 6).
-- Every catalog benchmark carries a difficulty tier (easy/medium/hard) and a
-- version so the Benchmark Registry can report coverage and reproducibility.

alter table benchmarks add column if not exists difficulty text not null default 'easy';
alter table benchmarks add column if not exists registry_version int not null default 1;

comment on column benchmarks.difficulty is
  'Difficulty tier of the benchmark (easy, medium, hard).';
comment on column benchmarks.registry_version is
  'Version of this benchmark entry in the BioNexus Benchmark Registry.';