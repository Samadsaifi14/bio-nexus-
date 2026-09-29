'use client';

import { useState, type FormEvent } from 'react';
import { ArrowRight, CircleNotch, DownloadSimple, MagnifyingGlass, Warning } from '@phosphor-icons/react';
import { resolveGeo, type GeoRecord } from '@/lib/api';

function saveSamples(record: GeoRecord) {
  const clean = (value: string) => value.replace(/[\t\r\n]+/g, ' ').trim();
  const rows = ['sample\tcondition\ttitle', ...record.samples.map(sample =>
    `${sample.accession}\t\t${clean(sample.title)}`)];
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([rows.join('\n') + '\n'], { type: 'text/tab-separated-values' }));
  link.download = `${record.accession}_sample_metadata.tsv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

export function GeoEntry({ onRna, onDna }: { onRna: () => void; onDna: () => void }) {
  const [value, setValue] = useState('');
  const [record, setRecord] = useState<GeoRecord | null>(null);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState('');

  const search = async (event: FormEvent) => {
    event.preventDefault();
    const accession = value.trim().toUpperCase();
    setError(''); setRecord(null);
    if (!/^(GSE|GSM|GDS|GPL)\d{1,9}$/.test(accession)) {
      setError('Enter a GEO accession such as GSE12345 or GSM12345.');
      return;
    }
    setPending(true);
    try { setRecord(await resolveGeo(accession)); }
    catch (caught: unknown) {
      const response = caught as { response?: { data?: { detail?: string } } };
      setError(response.response?.data?.detail || 'The GEO record could not be loaded. Try again.');
    } finally { setPending(false); }
  };

  return (
    <section className="data-card overflow-hidden" aria-labelledby="geo-title">
      <div className="border-b border-glass-border p-5 sm:p-6">
        <p className="font-mono text-[10px] uppercase tracking-[0.15em] text-accent-cyan">Public data entry</p>
        <h2 id="geo-title" className="mt-1 text-lg font-semibold text-text-primary">Start with a GEO accession</h2>
        <p className="mt-1 max-w-2xl text-xs leading-5 text-text-muted">Find a series, sample, dataset or platform. Inspect the real assay, samples and available files before choosing a sequencing or expression workflow.</p>
        <form onSubmit={search} className="mt-5 flex max-w-2xl flex-col gap-2 sm:flex-row">
          <label htmlFor="geo-accession" className="sr-only">GEO accession</label>
          <input id="geo-accession" value={value} onChange={event => setValue(event.target.value)} placeholder="GSE47774, GSM12345, GDS1234, GPL1234" autoComplete="off" spellCheck={false} className="min-w-0 flex-1 rounded-xl border border-glass-border bg-surface-1 px-4 py-3 font-mono text-sm text-text-primary outline-none transition focus:border-accent-cyan" />
          <button type="submit" disabled={pending} className="inline-flex items-center justify-center gap-2 rounded-xl bg-accent-cyan/15 px-5 py-3 text-sm font-semibold text-text-primary transition hover:bg-accent-cyan/25 disabled:opacity-50">{pending ? <CircleNotch className="animate-spin" /> : <MagnifyingGlass />} {pending ? 'Looking up…' : 'Find data'}</button>
        </form>
        {error && <div role="alert" className="mt-3 text-xs text-error"><p className="flex items-start gap-2"><Warning className="mt-0.5 shrink-0" />{error}</p>{/^(GSE|GSM|GDS|GPL)\d{1,9}$/.test(value.trim().toUpperCase()) && <a href={`https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${value.trim().toUpperCase()}`} target="_blank" rel="noopener noreferrer" className="ml-6 mt-1 inline-block underline underline-offset-2">Check this accession at NCBI ↗</a>}</div>}
      </div>

      {record && <div className="space-y-5 p-5 sm:p-6" aria-live="polite">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-3xl"><p className="font-mono text-xs text-accent-cyan">{record.accession} · {record.kind}</p><h3 className="mt-1 text-base font-semibold text-text-primary">{record.title || 'Untitled GEO record'}</h3><p className="mt-2 text-xs leading-5 text-text-secondary">{record.assay || 'Assay unspecified'}{record.organism && ` · ${record.organism}`}</p></div>
          <a href={record.url} target="_blank" rel="noopener noreferrer" className="rounded-lg border border-glass-border px-3 py-2 text-xs text-text-secondary hover:text-text-primary">View source ↗</a>
        </div>
        {record.summary && <p className="max-w-4xl text-xs leading-6 text-text-muted">{record.summary}</p>}
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="rounded-xl border border-glass-border bg-surface-1 p-4"><p className="text-[10px] uppercase tracking-widest text-text-muted">Samples in record</p><p className="mt-2 font-mono text-xl text-text-primary">{record.sample_count}</p></div>
          <div className="rounded-xl border border-glass-border bg-surface-1 p-4"><p className="text-[10px] uppercase tracking-widest text-text-muted">Sequencing assay</p><p className="mt-2 text-sm text-text-primary">{record.is_sequencing ? 'Indicated by GEO' : 'Not indicated'}</p></div>
          <div className="rounded-xl border border-glass-border bg-surface-1 p-4"><p className="text-[10px] uppercase tracking-widest text-text-muted">Supplementary files</p><p className="mt-2 font-mono text-xl text-text-primary">{record.files.length}</p></div>
        </div>
        {record.samples.length > 0 && <div><div className="flex flex-wrap items-center justify-between gap-2"><h4 className="text-sm font-semibold text-text-primary">Samples <span className="font-normal text-text-muted">(first {record.samples.length})</span></h4><button onClick={() => saveSamples(record)} className="inline-flex items-center gap-2 rounded-lg border border-glass-border px-3 py-2 text-xs text-text-secondary"><DownloadSimple /> Metadata template</button></div><div className="mt-2 max-h-56 overflow-auto rounded-xl border border-glass-border divide-y divide-glass-border">{record.samples.map(sample => <div key={sample.accession} className="grid gap-1 px-3 py-2 text-xs sm:grid-cols-[110px_1fr]"><button type="button" onClick={() => setValue(sample.accession)} className="text-left font-mono text-accent-cyan hover:underline">{sample.accession}</button><span className="text-text-secondary">{sample.title}</span></div>)}</div><p className="mt-2 text-[11px] text-text-muted">Fill the condition column from the study design before using the template for differential expression.</p></div>}
        {record.files.length > 0 && <div><h4 className="text-sm font-semibold text-text-primary">Published files</h4><div className="mt-2 flex flex-wrap gap-2">{record.files.map(file => <a key={file.url} href={file.url} target="_blank" rel="noopener noreferrer" className="max-w-full truncate rounded-lg border border-glass-border px-3 py-2 text-xs text-text-secondary hover:text-text-primary" title={file.name}>{file.name} ↗</a>)}</div></div>}
        {record.relations.length > 0 && <p className="text-[11px] text-text-muted">Linked records: {record.relations.map(item => `${item.name}: ${item.target}`).join(' · ')}</p>}
        <div className="rounded-xl border border-glass-border bg-surface-1 p-4 text-xs leading-5 text-text-secondary">
          {record.kind === 'GPL' || record.kind === 'GDS' ? 'This record describes a platform or curated dataset. Open its linked study or sample for sequencing inputs.' : record.is_sequencing ? 'GEO metadata alone cannot generate read QC, variant calls or expression figures. Use the published raw reads in the appropriate production workflow. For RNA expression figures, supply raw integer counts and matching sample metadata with a valid study design.' : 'This record is not labeled as a sequencing assay. Check its study methods before using an NGS workflow.'}
        </div>
        {record.is_sequencing && /expression profiling/i.test(record.assay) && <button type="button" onClick={onRna} className="inline-flex items-center gap-2 text-xs font-medium text-accent-cyan hover:underline">Open count matrix and figures <ArrowRight /></button>}
        {record.is_sequencing && /genome variation profiling/i.test(record.assay) && <button type="button" onClick={onDna} className="inline-flex items-center gap-2 text-xs font-medium text-accent-cyan hover:underline">Open DNA sequencing workflow <ArrowRight /></button>}
      </div>}
    </section>
  );
}
