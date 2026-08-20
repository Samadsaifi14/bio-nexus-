'use client';

import { useEffect, useRef, useState } from 'react';

declare global {
  interface Window {
    igv: any;
  }
}

const IGV_CDN_URL = 'https://cdn.jsdelivr.net/npm/igv@3.8.5/dist/igv.min.js';

interface IGVBrowserProps {
  referenceUrl: string;
  bamUrl?: string;
  baiUrl?: string;
  samUrl?: string;
  vcfUrl?: string;
  locus?: string;
  className?: string;
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) {
      resolve();
      return;
    }
    const script = document.createElement('script');
    script.src = src;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error(`Failed to load ${src}`));
    document.head.appendChild(script);
  });
}

async function fetchBlobUrl(url: string, label: string): Promise<string> {
  console.log(`[IGV] Fetching ${label} from:`, url);
  const resp = await fetch(url);
  if (!resp.ok) throw new Error(`Failed to fetch ${label}: HTTP ${resp.status}`);
  const blob = await resp.blob();
  console.log(`[IGV] ${label} fetched: ${blob.size} bytes, type: ${blob.type}`);
  const blobUrl = URL.createObjectURL(blob);
  console.log(`[IGV] ${label} blob URL:`, blobUrl);
  return blobUrl;
}

export default function IGVBrowser({
  referenceUrl,
  bamUrl,
  baiUrl,
  samUrl,
  vcfUrl,
  locus,
  className = '',
}: IGVBrowserProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const browserRef = useRef<any>(null);
  const blobUrlsRef = useRef<string[]>([]);
  const [status, setStatus] = useState<'loading' | 'ready' | 'error'>('loading');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    if (!containerRef.current || !referenceUrl) return;
    let cancelled = false;

    async function init() {
      try {
        setStatus('loading');
        setErrorMsg('');

        // Clean up previous blob URLs
        for (const u of blobUrlsRef.current) URL.revokeObjectURL(u);
        blobUrlsRef.current = [];

        // Load igv.js from CDN
        await loadScript(IGV_CDN_URL);
        if (cancelled || !containerRef.current) return;
        if (!window.igv) throw new Error('igv.js failed to load from CDN');

        // Destroy previous instance
        if (browserRef.current) {
          try { browserRef.current.destroy(); } catch {}
          browserRef.current = null;
        }
        containerRef.current.innerHTML = '';

        const tracks: any[] = [];

        // Fetch ALL files as Blobs first — eliminates CORS/encoding issues
        const blobUrlMap: Record<string, string> = {};

        // Reference FASTA
        try {
          blobUrlMap.reference = await fetchBlobUrl(referenceUrl, 'reference FASTA');
          blobUrlsRef.current.push(blobUrlMap.reference);
        } catch (e: any) {
          console.error('[IGV] Failed to fetch reference:', e);
          throw new Error(`Reference genome fetch failed: ${e.message}`);
        }

        // BAM + BAI — igv.js ONLY supports BAM/CRAM for alignment tracks, NOT SAM
        if (bamUrl && baiUrl) {
          try {
            blobUrlMap.bam = await fetchBlobUrl(bamUrl, 'BAM');
            blobUrlMap.bai = await fetchBlobUrl(baiUrl, 'BAI');
            blobUrlsRef.current.push(blobUrlMap.bam, blobUrlMap.bai);
          } catch (e: any) {
            console.warn('[IGV] BAM/BAI fetch failed, trying SAM fallback:', e.message);
          }
        }

        // If BAM failed or unavailable, try SAM as raw text → parse and convert client-side
        let samContent: string | null = null;
        if (!blobUrlMap.bam && samUrl) {
          try {
            console.log('[IGV] Fetching SAM as text...');
            const resp = await fetch(samUrl);
            if (resp.ok) {
              samContent = await resp.text();
              console.log(`[IGV] SAM fetched: ${samContent.length} chars`);
              console.log('[IGV] SAM first 200 chars:', samContent.substring(0, 200));
            }
          } catch (e: any) {
            console.warn('[IGV] SAM fetch failed:', e.message);
          }
        }

        // VCF
        if (vcfUrl) {
          try {
            blobUrlMap.vcf = await fetchBlobUrl(vcfUrl, 'VCF');
            blobUrlsRef.current.push(blobUrlMap.vcf);
          } catch (e: any) {
            console.warn('[IGV] VCF fetch failed:', e.message);
          }
        }

        console.log('[IGV] locus:', locus);
        console.log('[IGV] BAM blob URL:', blobUrlMap.bam || '(none)');
        console.log('[IGV] SAM content available:', !!samContent);

        // Build tracks
        if (blobUrlMap.bam && blobUrlMap.bai) {
          // BAM track — proper binary alignment format
          tracks.push({
            name: 'Aligned Reads (BAM)',
            url: blobUrlMap.bam,
            type: 'alignment',
            format: 'bam',
            indexURL: blobUrlMap.bai,
            color: '#3b82f6',
            height: 200,
            displayMode: 'expanded',
            indexed: true,
          });
        } else if (samContent) {
          // SAM client-side conversion: build a BAM in memory
          console.log('[IGV] Converting SAM to BAM client-side...');
          try {
            const bamBlob = convertSamToBamBlob(samContent);
            const bamBlobUrl = URL.createObjectURL(bamBlob);
            blobUrlsRef.current.push(bamBlobUrl);
            console.log(`[IGV] Client BAM: ${bamBlob.size} bytes`);

            tracks.push({
              name: 'Aligned Reads (SAM)',
              url: bamBlobUrl,
              type: 'alignment',
              format: 'bam',
              color: '#3b82f6',
              height: 200,
              displayMode: 'expanded',
              indexed: false,
            });
          } catch (e: any) {
            console.error('[IGV] Client-side SAM→BAM failed:', e);
          }
        }

        if (blobUrlMap.vcf) {
          tracks.push({
            name: 'Variants',
            url: blobUrlMap.vcf,
            format: 'vcf',
            type: 'variant',
            color: '#f59e0b',
            height: 120,
            displayMode: 'expanded',
            indexed: false,
          });
        }

        console.log('[IGV] Tracks:', tracks.map((t: any) => `${t.name}(${t.format})`));

        const browser = await window.igv.createBrowser(containerRef.current, {
          reference: {
            fastaURL: blobUrlMap.reference,
            indexed: false,
          },
          tracks,
          locus: locus || '1',
          showNavigation: true,
          showRuler: true,
        });

        if (!cancelled) {
          browserRef.current = browser;
          setStatus('ready');
          console.log('[IGV] Browser ready.');
        } else {
          try { browser.destroy(); } catch {}
        }
      } catch (err: any) {
        console.error('[IGV] Full error:', err);
        if (!cancelled) {
          setStatus('error');
          setErrorMsg(err?.message || 'Failed to initialize genome browser');
        }
      }
    }

    const timer = setTimeout(init, 200);

    return () => {
      cancelled = true;
      clearTimeout(timer);
      if (browserRef.current) {
        try { browserRef.current.destroy(); } catch {}
        browserRef.current = null;
      }
      for (const u of blobUrlsRef.current) URL.revokeObjectURL(u);
      blobUrlsRef.current = [];
    };
  }, [referenceUrl, bamUrl, baiUrl, samUrl, vcfUrl, locus]);

  return (
    <div className={className}>
      {status === 'loading' && (
        <div className="flex items-center justify-center py-12 bg-surface-1 rounded-xl">
          <div className="w-5 h-5 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
          <span className="ml-3 text-sm text-text-muted">Loading genome browser...</span>
        </div>
      )}
      <div
        ref={containerRef}
        style={{
          width: '100%',
          minHeight: status === 'ready' ? '500px' : '0px',
          display: status === 'loading' ? 'none' : 'block',
        }}
      />
      {status === 'error' && (
        <div className="p-4 bg-error/5 border border-error/20 rounded-xl mt-2">
          <p className="text-sm text-error font-medium">Genome browser failed to load</p>
          <p className="text-xs text-error/70 mt-1 font-mono">{errorMsg}</p>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Client-side SAM → BAM converter (minimal, for igv.js compatibility)
// Produces a single-BGZF-block BAM file as a Blob.
// ---------------------------------------------------------------------------

function convertSamToBamBlob(samText: string): Blob {
  const lines = samText.split('\n').filter(l => l.length > 0);
  const headerLines: string[] = [];
  const samRecords: string[] = [];

  for (const line of lines) {
    if (line.startsWith('@')) {
      headerLines.push(line);
    } else if (line.trim().length > 0) {
      samRecords.push(line);
    }
  }

  // Parse header
  const refNames: string[] = [];
  const refLengths: number[] = [];
  let headerText = '';

  for (const hl of headerLines) {
    if (hl.startsWith('@SQ')) {
      const parts = hl.split('\t');
      let name = '';
      let length = 0;
      for (const p of parts.slice(1)) {
        if (p.startsWith('SN:')) name = p.slice(3);
        else if (p.startsWith('LN:')) length = parseInt(p.slice(3));
      }
      if (name) {
        refNames.push(name);
        refLengths.push(length);
        headerText += hl + '\n';
      }
    } else if (hl.startsWith('@HD') || hl.startsWith('@RG') || hl.startsWith('@PG')) {
      headerText += hl + '\n';
    }
  }

  const refIdMap = new Map(refNames.map((n, i) => [n, i]));

  // Build BAM header bytes
  const hdrBytes = new TextEncoder().encode(headerText);
  const refDictParts: number[] = [];

  for (let i = 0; i < refNames.length; i++) {
    const nameBytes = new TextEncoder().encode(refNames[i] + '\x00');
    refDictParts.push(nameBytes.length);
    // We'll collect all bytes below
  }

  // Build ref dictionary as bytes
  let refDictBytes = new Uint8Array(0);
  for (let i = 0; i < refNames.length; i++) {
    const nameBytes = new TextEncoder().encode(refNames[i] + '\x00');
    const nameLenBuf = new Uint8Array(4);
    new DataView(nameLenBuf.buffer).setUint32(0, nameBytes.length, true);
    const refLenBuf = new Uint8Array(4);
    new DataView(refLenBuf.buffer).setInt32(0, refLengths[i], true);
    const merged = new Uint8Array(refDictBytes.length + nameLenBuf.length + nameBytes.length + refLenBuf.length);
    merged.set(refDictBytes, 0);
    merged.set(nameLenBuf, refDictBytes.length);
    merged.set(nameBytes, refDictBytes.length + nameLenBuf.length);
    merged.set(refLenBuf, refDictBytes.length + nameLenBuf.length + nameBytes.length);
    refDictBytes = merged;
  }

  const nRefBuf = new Uint8Array(4);
  new DataView(nRefBuf.buffer).setUint32(0, refNames.length, true);

  const hdrLenBuf = new Uint8Array(4);
  new DataView(hdrLenBuf.buffer).setUint32(0, hdrBytes.length, true);

  const magicBytes = new TextEncoder().encode('BAM\x01');

  // Concatenate header
  const bamHeader = concatBytes([magicBytes, hdrLenBuf, hdrBytes, nRefBuf, refDictBytes]);

  // Build alignment records
  let allRecords = new Uint8Array(0);

  const BASES: Record<string, number> = { A: 0, C: 1, G: 2, T: 3, N: 4 };
  const OP_MAP: Record<string, number> = { M: 0, I: 1, D: 2, N: 3, S: 4, H: 5, P: 6, '=': 7, X: 8 };

  for (const line of samRecords) {
    const parts = line.split('\t');
    if (parts.length < 11) continue;

    const qname = parts[0];
    const flag = parseInt(parts[1]);
    const rname = parts[2];
    const pos = parseInt(parts[3]) - 1; // SAM 1-based → BAM 0-based
    const mapq = parseInt(parts[4]);
    const cigarStr = parts[5];
    const rnext = parts[6];
    const pnext = parseInt(parts[7]);
    const seq = parts[9];
    const qualStr = parts[10];

    let refId = refIdMap.get(rname) ?? -1;
    if (rname === '*') refId = -1;

    let nextRefId = refIdMap.get(rnext) ?? -1;
    if (rnext === '=') nextRefId = refId;
    else if (rnext === '*') nextRefId = -1;

    // Parse CIGAR
    const cigarOps: [number, number][] = [];
    if (cigarStr !== '*') {
      const cigarRe = /(\d+)([MIDNSHUPX=])/g;
      let m;
      while ((m = cigarRe.exec(cigarStr)) !== null) {
        cigarOps.push([parseInt(m[1]), OP_MAP[m[2]] ?? 0]);
      }
    }

    // Encode sequence (4-bit)
    const seqEnc = new Uint8Array(Math.ceil(seq.length / 2));
    for (let i = 0; i < seq.length; i += 2) {
      const hi = (BASES[seq[i]?.toUpperCase()] ?? 4) << 4;
      const lo = i + 1 < seq.length ? (BASES[seq[i + 1]?.toUpperCase()] ?? 4) : 0;
      seqEnc[i >> 1] = hi | lo;
    }

    // Quality
    let qualEnc: Uint8Array;
    if (qualStr && qualStr !== '*') {
      qualEnc = new Uint8Array(qualStr.length);
      for (let i = 0; i < qualStr.length; i++) {
        qualEnc[i] = Math.min(qualStr.charCodeAt(i) - 33, 93);
      }
    } else {
      qualEnc = new Uint8Array(seq.length).fill(255);
    }

    // CIGAR as uint32 array
    const cigarEnc = new Uint8Array(cigarOps.length * 4);
    const cigarView = new DataView(cigarEnc.buffer);
    for (let i = 0; i < cigarOps.length; i++) {
      cigarView.setUint32(i * 4, (cigarOps[i][0] << 4) | cigarOps[i][1], true);
    }

    // Read name (null-terminated, padded to 4 bytes)
    const qnameBytes = new TextEncoder().encode(qname + '\x00');
    const qnamePaddedLen = Math.ceil(qnameBytes.length / 4) * 4;
    const qnamePadded = new Uint8Array(qnamePaddedLen);
    qnamePadded.set(qnameBytes);

    // Compute bin
    const refEnd = pos + cigarOps.reduce((s, [l, op]) => s + ([0, 2, 3].includes(op) ? l : 0), 0) || pos + seq.length;
    const recBin = refId >= 0 ? reg2bin(pos, refEnd) : 0;

    const nCigar = cigarOps.length;
    const lSeq = seq.length;
    const binMqNl = (recBin << 16) | (mapq << 8) | qnameBytes.length;

    // Build record
    const recParts: Uint8Array[] = [];
    recParts.push(i32(refId));
    recParts.push(i32(pos));
    recParts.push(u32(binMqNl));
    recParts.push(u32(flag));
    recParts.push(u32(nCigar));
    recParts.push(u32(lSeq));
    recParts.push(i32(nextRefId));
    recParts.push(i32(pnext));
    recParts.push(i32(0)); // tlen
    recParts.push(qnamePadded);
    recParts.push(cigarEnc);
    recParts.push(seqEnc);
    recParts.push(qualEnc);

    const record = concatBytes(recParts);
    const recLenBuf = new Uint8Array(4);
    new DataView(recLenBuf.buffer).setUint32(0, record.length, true);

    const recWithLen = new Uint8Array(4 + record.length);
    recWithLen.set(recLenBuf, 0);
    recWithLen.set(record, 4);

    const newRecords = new Uint8Array(allRecords.length + recWithLen.length);
    newRecords.set(allRecords, 0);
    newRecords.set(recWithLen, allRecords.length);
    allRecords = newRecords;
  }

  // Full uncompressed BAM
  const rawBam = concatBytes([bamHeader, allRecords]);

  // BGZF compress
  const bgzfBlock = bgzfCompress(rawBam);

  const buf = bgzfBlock.buffer.slice(bgzfBlock.byteOffset, bgzfBlock.byteOffset + bgzfBlock.byteLength) as ArrayBuffer;
  return new Blob([buf], { type: 'application/octet-stream' });
}

// --- Helpers ---

function concatBytes(arrays: Uint8Array[]): Uint8Array {
  let total = 0;
  for (const a of arrays) total += a.length;
  const result = new Uint8Array(total);
  let offset = 0;
  for (const a of arrays) {
    result.set(a, offset);
    offset += a.length;
  }
  return result;
}

function i32(v: number): Uint8Array {
  const buf = new Uint8Array(4);
  new DataView(buf.buffer).setInt32(0, v, true);
  return buf;
}

function u32(v: number): Uint8Array {
  const buf = new Uint8Array(4);
  new DataView(buf.buffer).setUint32(0, v, true);
  return buf;
}

function reg2bin(beg: number, end: number): number {
  end -= 1;
  if ((beg >> 14) === (end >> 14)) return ((1 << 15) - 1) / 7 + (beg >> 14);
  if ((beg >> 17) === (end >> 17)) return ((1 << 12) - 1) / 7 + (beg >> 17);
  if ((beg >> 20) === (end >> 20)) return ((1 << 9) - 1) / 7 + (beg >> 20);
  if ((beg >> 23) === (end >> 23)) return ((1 << 6) - 1) / 7 + (beg >> 23);
  if ((beg >> 26) === (end >> 26)) return ((1 << 3) - 1) / 7 + (beg >> 26);
  return 0;
}

function bgzfCompress(data: Uint8Array): Uint8Array {
  // Use pako if available, otherwise raw deflate via gzip
  // We need to produce a valid BGZF block

  // For the browser, we'll use the built-in CompressionStream API
  // But it's async. Instead, use a simple deflate via a prelude.
  // Actually, let's use pako-style raw deflate with a minimal approach:
  // The simplest approach: use gzip format (not BGZF) and set format: 'bam'
  // Wait, igv.js REQUIRES BGZF.

  // Use zlib raw deflate via the CompressionStream API
  // But we need sync... Let's just use the fact that pako is bundled in igv.js

  // Actually the cleanest approach: encode the data as a base64 string and
  // construct a BAM file in memory using igv.js's own utilities.
  // But that's complex. Let's do raw deflate manually.

  // For a simple implementation, use gzip wrapper (which igv.js treats as single-block BGZF)
  return gzipBlock(data);
}

function adler32(data: Uint8Array): number {
  let a = 1, b = 0;
  for (let i = 0; i < data.length; i++) {
    a = (a + data[i]) % 65521;
    b = (b + a) % 65521;
  }
  return (b << 16) | a;
}

function crc32Table(): Uint32Array {
  const table = new Uint32Array(256);
  for (let i = 0; i < 256; i++) {
    let c = i;
    for (let j = 0; j < 8; j++) {
      c = (c & 1) ? (0xEDB88320 ^ (c >>> 1)) : (c >>> 1);
    }
    table[i] = c;
  }
  return table;
}

const CRC_TABLE = crc32Table();

function crc32(data: Uint8Array): number {
  let crc = 0xFFFFFFFF;
  for (let i = 0; i < data.length; i++) {
    crc = CRC_TABLE[(crc ^ data[i]) & 0xFF] ^ (crc >>> 8);
  }
  return (crc ^ 0xFFFFFFFF) >>> 0;
}

function gzipBlock(data: Uint8Array): Uint8Array {
  // Gzip format: header + deflate compressed data + CRC32 + ISIZE
  // We store the raw deflate output in a Uint8Array, then wrap it

  // For proper BGZF, we need to compute a raw deflate stream.
  // The simplest way in browser is via pako, but it may not be available.
  // So we produce a STORE block (no compression) wrapped in BGZF headers.
  // This makes the file larger but ensures correctness.

  // Actually, igv.js needs BGZF specifically. Let's use a minimal DEFLATE:
  // Store blocks with BFINAL=1.

  const rawDeflate = storeDeflate(data);

  // BGZF block = gzip header + extra(BGZF metadata) + deflate data + CRC32 + ISIZE
  // Total block size: we need to compute this.
  // Gzip header: 10 bytes (ID1,ID2,CM,FLG,MTIME[4],XFL,OS)
  // Extra field: 2 bytes XLEN + 10 bytes subfield = 12 bytes
  // Deflate data: rawDeflate.length bytes
  // CRC32: 4 bytes
  // ISIZE: 4 bytes

  const XLEN = 10;
  const EXTRA_SIZE = 2 + XLEN; // XLEN field + subfield
  const blockTotalSize = 10 + EXTRA_SIZE + rawDeflate.length + 4 + 4;
  const bsize = blockTotalSize - 1;
  const cdlen = rawDeflate.length - 1;

  // Build block
  const block = new Uint8Array(blockTotalSize);
  const dv = new DataView(block.buffer);

  // Gzip header (10 bytes)
  block[0] = 0x1f; // ID1
  block[1] = 0x8b; // ID2
  block[2] = 0x08; // CM = deflate
  block[3] = 0x04; // FLG = FEXTRA
  dv.setUint32(4, 0, true); // MTIME
  block[8] = 0x00; // XFL
  block[9] = 0x00; // OS

  // XLEN
  dv.setUint16(10, XLEN, true);

  // Extra subfield: SI1='B', SI2='C', SLEN=6, BSIZE, CDLEN, RN
  block[12] = 0x42; // 'B'
  block[13] = 0x43; // 'C'
  dv.setUint16(14, 6, true); // SLEN
  dv.setUint16(16, bsize, true); // BSIZE
  dv.setUint16(18, cdlen, true); // CDLEN
  dv.setUint16(20, 0, true); // RN

  // Deflate data
  block.set(rawDeflate, 22);

  // CRC32
  const crcValue = crc32(data);
  dv.setUint32(22 + rawDeflate.length, crcValue, true);

  // ISIZE
  dv.setUint32(26 + rawDeflate.length, data.length, true);

  return block;
}

function storeDeflate(data: Uint8Array): Uint8Array {
  // Produce a STORE (no compression) deflate stream.
  // DEFLATE STORE format:
  //   Block header byte: BFINAL(1 bit) + BTYPE=00(2 bits) + skip remaining bits in byte
  //   LEN (2 bytes LE): length of literal data (max 65535)
  //   NLEN (2 bytes LE): ones complement of LEN
  //   Literal data bytes
  // Then flush for final block.

  const MAX_BLOCK = 65535;
  const blocks: Uint8Array[] = [];
  let offset = 0;

  while (offset < data.length) {
    const remaining = data.length - offset;
    const blockLen = Math.min(remaining, MAX_BLOCK);
    const isFinal = offset + blockLen >= data.length;

    // Block header: BFINAL(bit0) + BTYPE=00(bits1-2) = 0x00 or 0x01
    const headerByte = isFinal ? 0x01 : 0x00;
    const header = new Uint8Array([headerByte]);

    const lenBuf = new Uint8Array(4);
    const lenDv = new DataView(lenBuf.buffer);
    lenDv.setUint16(0, blockLen, true);
    lenDv.setUint16(2, blockLen ^ 0xFFFF, true);

    blocks.push(header, lenBuf, data.slice(offset, offset + blockLen));
    offset += blockLen;
  }

  return concatBytes(blocks);
}
