import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

type GeoSample = { accession: string; title: string };
type GeoFile = { name: string; url: string };
type GeoSummary = Record<string, unknown>;

const accessionPattern = /^(GSE|GSM|GDS|GPL)\d{1,9}$/i;
const eutils = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils';

function text(value: unknown, limit: number): string {
  return typeof value === 'string' ? value.slice(0, limit) : '';
}

function accessionDirectory(accession: string): string | null {
  const prefix = accession.slice(0, 3);
  if (prefix !== 'GSE' && prefix !== 'GSM') return null;
  const digits = accession.slice(3);
  const block = `${prefix}${digits.length > 3 ? digits.slice(0, -3) : ''}nnn`;
  return `https://ftp.ncbi.nlm.nih.gov/geo/${prefix === 'GSE' ? 'series' : 'samples'}/${block}/${accession}/suppl/`;
}

async function publicFiles(accession: string): Promise<GeoFile[]> {
  const directory = accessionDirectory(accession);
  if (!directory) return [];
  try {
    const response = await fetch(directory, { signal: AbortSignal.timeout(8000), cache: 'no-store' });
    if (!response.ok) return [];
    const html = (await response.text()).slice(0, 500_000);
    const names = [...html.matchAll(/href=["']([^"']+)["']/gi)]
      .map(match => { try { return decodeURIComponent(match[1]); } catch { return ''; } })
      .filter(name => name && !name.includes('/') && !name.includes('\\') && !name.includes('?') && !name.includes('#') && name !== '..');
    return [...new Set(names)].slice(0, 40).map(name => ({ name, url: directory + encodeURIComponent(name) }));
  } catch { return []; }
}

async function directGeoRecord(accession: string): Promise<GeoSummary | null> {
  const url = new URL('https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi');
  url.search = new URLSearchParams({ acc: accession, targ: 'self', form: 'text', view: 'quick' }).toString();
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(10000), cache: 'no-store' });
    if (!response.ok) return null;
    const content = (await response.text()).slice(0, 1_000_000);
    const type = { GSE: 'Series', GSM: 'Sample', GDS: 'Dataset', GPL: 'Platform' }[accession.slice(0, 3) as 'GSE' | 'GSM' | 'GDS' | 'GPL'];
    if (!content.split(/\r?\n/).some(line => line.trim().toUpperCase() === `^${type.toUpperCase()} = ${accession}`)) return null;
    const fields = new Map<string, string[]>();
    for (const line of content.split(/\r?\n/)) {
      const match = line.match(/^!([A-Za-z]+)_([^=]+)\s*=\s*(.*)$/);
      if (!match || match[1].toLowerCase() !== type.toLowerCase()) continue;
      const key = match[2].trim().toLowerCase();
      fields.set(key, [...(fields.get(key) ?? []), match[3].trim()]);
    }
    const sampleIds = (fields.get('sample_id') ?? []).filter(value => /^GSM\d+$/i.test(value)).slice(0, 200);
    return {
      accession, title: fields.get('title')?.[0] ?? '', summary: (fields.get('summary') ?? []).join(' '),
      gdstype: (fields.get('type') ?? []).join(' · '), taxon: fields.get('organism')?.[0] ?? '',
      n_samples: sampleIds.length, samples: sampleIds.map(id => ({ accession: id, title: '' })),
      supplementary_urls: fields.get('supplementary_file') ?? [],
    };
  } catch { return null; }
}

async function eutilsRecord(accession: string): Promise<GeoSummary | null> {
  const query = new URLSearchParams({ db: 'gds', term: `${accession}[ACCN]`, retmode: 'json', retmax: '25', tool: 'bionexus' });
  const search = await fetch(`${eutils}/esearch.fcgi?${query}`, { signal: AbortSignal.timeout(12000), cache: 'no-store' });
  if (!search.ok) throw new Error('NCBI GEO search failed');
  const ids: unknown = (await search.json()).esearchresult?.idlist;
  if (!Array.isArray(ids) || !ids.every(id => typeof id === 'string')) throw new Error('Invalid NCBI search response');
  if (!ids.length) return null;
  const params = new URLSearchParams({ db: 'gds', id: ids.join(','), retmode: 'json', tool: 'bionexus' });
  const summary = await fetch(`${eutils}/esummary.fcgi?${params}`, { signal: AbortSignal.timeout(12000), cache: 'no-store' });
  if (!summary.ok) throw new Error('NCBI GEO summary failed');
  const result = (await summary.json()).result as Record<string, GeoSummary>;
  return ids.map(id => result?.[id]).find(row => text(row?.accession, 20).toUpperCase() === accession) ?? null;
}

async function fillSampleTitles(accession: string, samples: GeoSample[]): Promise<GeoSample[]> {
  if (!accession.startsWith('GSE') || !samples.length || samples.length > 100 || samples.some(item => item.title)) return samples;
  const url = new URL('https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi');
  url.search = new URLSearchParams({ acc: accession, targ: 'gsm', form: 'text', view: 'brief' }).toString();
  try {
    const response = await fetch(url, { signal: AbortSignal.timeout(12000), cache: 'no-store' });
    if (!response.ok) return samples;
    const body = (await response.text()).slice(0, 2_000_000);
    const titles = new Map<string, string>();
    let current = '';
    for (const line of body.split(/\r?\n/)) {
      const marker = line.match(/^\^SAMPLE = (GSM\d+)$/);
      if (marker) current = marker[1];
      const title = line.match(/^!Sample_title\s*=\s*(.+)$/);
      if (current && title) titles.set(current, title[1].slice(0, 300));
    }
    return samples.map(item => ({ ...item, title: titles.get(item.accession) ?? item.title }));
  } catch { return samples; }
}

export async function GET(_request: NextRequest, context: { params: Promise<{ accession: string }> }) {
  const accession = (await context.params).accession.trim().toUpperCase();
  if (!accessionPattern.test(accession)) return NextResponse.json({ detail: 'Enter a valid GSE, GSM, GDS or GPL accession.' }, { status: 422 });

  let record: GeoSummary | null = null;
  try { record = await eutilsRecord(accession); }
  catch { /* Try GEO's direct accession record when Entrez is unavailable. */ }
  if (!record) record = await directGeoRecord(accession);
  if (!record) return NextResponse.json({
    detail: `GEO could not confirm a public record for ${accession}. It may be private, not released yet, or temporarily unavailable. Check the accession at NCBI.`,
    url: `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${accession}`,
  }, { status: 404 });

  const indexedSamples: GeoSample[] = Array.isArray(record.samples) ? record.samples
    .filter((item): item is GeoSummary => typeof item === 'object' && item !== null)
    .filter(item => /^GSM\d+$/i.test(text(item.accession, 30)))
    .slice(0, 200).map(item => ({ accession: text(item.accession, 30), title: text(item.title, 300) })) : [];
  const samples = await fillSampleTitles(accession, indexedSamples);
  const rawRelations = Array.isArray(record.extrelations) ? record.extrelations : Array.isArray(record.relations) ? record.relations : [];
  const relations = rawRelations.slice(0, 30).filter((item): item is GeoSummary => typeof item === 'object' && item !== null)
    .map(item => ({ name: text(item.name, 80), target: text(item.target, 80) }));
  const assay = text(record.gdstype ?? record.gdsType, 200);
  const count = Number(record.n_samples ?? record.nSamples ?? samples.length);
  let files = await publicFiles(accession);
  if (!files.length && accession.startsWith('GS')) {
    const direct = record.supplementary_urls ? record : await directGeoRecord(accession);
    const urls = Array.isArray(direct?.supplementary_urls) ? direct.supplementary_urls : [];
    const directory = accessionDirectory(accession);
    files = urls.map(value => {
      const raw = text(value, 700).replace(/^ftp:\/\//i, 'https://');
      try {
        const url = new URL(raw);
        const name = decodeURIComponent(url.pathname.split('/').at(-1) ?? '');
        return directory && url.hostname === 'ftp.ncbi.nlm.nih.gov' && url.href.startsWith(directory)
          && /^[A-Za-z0-9_.-]{1,180}$/.test(name) ? { name, url: directory + encodeURIComponent(name) } : null;
      } catch { return null; }
    }).filter((file): file is GeoFile => file !== null).slice(0, 40);
  }
  return NextResponse.json({
    accession, kind: accession.slice(0, 3), title: text(record.title, 500), summary: text(record.summary, 2000),
    assay, organism: text(record.taxon ?? record.taxonname, 160),
    sample_count: Number.isFinite(count) && count >= 0 ? count : samples.length,
    samples, files, relations,
    url: `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${accession}`,
    is_sequencing: /sequencing/i.test(assay),
  });
}
