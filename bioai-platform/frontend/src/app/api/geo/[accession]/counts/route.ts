import { NextRequest, NextResponse } from 'next/server';

export const runtime = 'nodejs';

const MAX_COMPRESSED = 3_500_000;

export async function GET(request: NextRequest, context: { params: Promise<{ accession: string }> }) {
  const accession = (await context.params).accession.toUpperCase();
  const filename = request.nextUrl.searchParams.get('file') ?? '';
  if (!/^GSE\d{1,9}$/.test(accession) || !/^[A-Za-z0-9_.-]{1,180}\.(csv|tsv|txt)(\.gz)?$/i.test(filename)) {
    return NextResponse.json({ detail: 'Choose a GEO series and a plain-text count matrix.' }, { status: 422 });
  }
  if (!/count/i.test(filename) || /(fpkm|tpm|rpkm|normalized|normalised|log2?|vst|rlog)/i.test(filename)) {
    return NextResponse.json({ detail: 'DESeq2 requires a raw integer count matrix; normalized expression files cannot be used.' }, { status: 422 });
  }

  const digits = accession.slice(3);
  const block = `GSE${digits.length > 3 ? digits.slice(0, -3) : ''}nnn`;
  const directory = `https://ftp.ncbi.nlm.nih.gov/geo/series/${block}/${accession}/suppl/`;
  try {
    // Confirm this filename is published under the accession before fetching it.
    const html = await fetch(directory, { signal: AbortSignal.timeout(10000), cache: 'no-store' })
      .then(response => response.ok ? response.text() : '').then(value => value.slice(0, 500_000)).catch(() => '');
    let listed = [...html.matchAll(/href=["']([^"']+)["']/gi)].some(match => {
      try { return decodeURIComponent(match[1]) === filename; } catch { return false; }
    });
    if (!listed) {
      const url = new URL('https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi');
      url.search = new URLSearchParams({ acc: accession, targ: 'self', form: 'text', view: 'brief' }).toString();
      const soft = await fetch(url, { signal: AbortSignal.timeout(10000), cache: 'no-store' });
      if (soft.ok) {
        const content = (await soft.text()).slice(0, 500_000);
        listed = content.includes(`^SERIES = ${accession}`) && content.split(/\r?\n/).some(line => {
          if (!line.startsWith('!Series_supplementary_file = ')) return false;
          try { const item = new URL(line.split(' = ').slice(1).join(' = ').replace(/^ftp:\/\//i, 'https://')); return item.hostname === 'ftp.ncbi.nlm.nih.gov' && item.pathname === new URL(directory + encodeURIComponent(filename)).pathname; }
          catch { return false; }
        });
      }
    }
    if (!listed) return NextResponse.json({ detail: 'This count file is not listed under that GEO accession.' }, { status: 404 });

    const upstream = await fetch(directory + encodeURIComponent(filename), { signal: AbortSignal.timeout(30000), cache: 'no-store' });
    if (!upstream.ok || !upstream.body) throw new Error('The published count file could not be downloaded');
    if (Number(upstream.headers.get('content-length') ?? 0) > MAX_COMPRESSED) {
      return NextResponse.json({ detail: 'This matrix exceeds the interactive download limit. Use the published file with the upload analysis.' }, { status: 413 });
    }
    const reader = upstream.body.getReader();
    const parts: Uint8Array[] = [];
    let total = 0;
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_COMPRESSED) {
        await reader.cancel();
        return NextResponse.json({ detail: 'This matrix exceeds the interactive download limit. Use the published file with the upload analysis.' }, { status: 413 });
      }
      parts.push(value);
    }
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const part of parts) { bytes.set(part, offset); offset += part.byteLength; }
    return new NextResponse(bytes, {
      headers: {
        'Content-Type': filename.endsWith('.gz') ? 'application/gzip' : 'text/plain; charset=utf-8',
        'Content-Disposition': `attachment; filename="${filename}"`,
        'Cache-Control': 'private, no-store',
        'X-Content-Type-Options': 'nosniff',
      },
    });
  } catch {
    return NextResponse.json({ detail: 'The NCBI count file could not be retrieved right now. Try again or download it from GEO.' }, { status: 502 });
  }
}
