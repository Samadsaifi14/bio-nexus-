import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';
const code = ts.transpileModule(readFileSync(new URL('../src/lib/rnaseqPlotData.ts', import.meta.url), 'utf8'),
  { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
const { evidencePoints, loadPlotEvidence, parsePlotTsv } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));

const rows = parsePlotTsv('gene\tlog2FoldChange\tminus_log10_padj\tpadj\tdirection\ng1\t0\t0\t1\tNS\ng2\t\t2\t0.01\tUP\ng3\t1\t\t0.1\tNS\n');
const parsed = evidencePoints(rows, 'volcano', 'direction');
assert.equal(parsed.points.length, 1);
assert.equal(parsed.excluded, 2);
assert.deepEqual([parsed.points[0].x, parsed.points[0].y], [0, 0]);
assert.throws(() => evidencePoints([rows[0], rows[0]], 'volcano', 'direction'), /duplicate/);
assert.throws(() => parsePlotTsv('gene\tgene\nx\ty'), /header/);
assert.throws(() => parsePlotTsv('gene\tvalue\nx\t1\t2'), /column count/);
assert.equal(evidencePoints(parsePlotTsv('sample\tPC1\tPC2\tbatch\ns1\t-3\t4\tb1'), 'pca', 'batch').points[0].group, 'b1');
const bytes = new TextEncoder().encode('sample\tPC1\tPC2\ns1\t0\t1\n');
const sha256 = Buffer.from(await crypto.subtle.digest('SHA-256', bytes)).toString('hex');
const item = { name: 'pca_coordinates.tsv', bytes: bytes.length, sha256, url: 'https://example.invalid/pca.tsv' };
const original = globalThis.fetch;
try {
  globalThis.fetch = async () => new Response(bytes);
  assert.equal((await loadPlotEvidence(item, new AbortController().signal))[0].sample, 's1');
  await assert.rejects(loadPlotEvidence({ ...item, sha256: '0'.repeat(64) }, new AbortController().signal), /checksum/);
  await assert.rejects(loadPlotEvidence({ ...item, bytes: bytes.length - 1 }, new AbortController().signal), /byte count/);
  await assert.rejects(loadPlotEvidence({ ...item, bytes: bytes.length + 1 }, new AbortController().signal), /incomplete/);
} finally { globalThis.fetch = original; }
console.log('RNA-seq plot identity, missingness, metadata and checksum checks passed');
