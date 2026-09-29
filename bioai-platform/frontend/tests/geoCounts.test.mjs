import test from 'node:test';
import assert from 'node:assert/strict';
import { gzipSync } from 'node:zlib';
import { prepareGeoCounts } from '../src/lib/geoCounts.ts';

const sampleIds = Array.from({ length: 10 }, (_, index) => `GSM984429${index}`);
const libraries = ['GZ23094742', 'GZ23094741', 'GZ23094725', 'GZ23094724', 'GZ23094709', 'GZ23094732', 'GZ23094731', 'GZ23094729', 'GZ23094716', 'GZ23090348'];
const record = {
  accession: 'GSE336901',
  samples: sampleIds.map((accession, index) => ({ accession, title: `FFPE ${index < 5 ? 'sensitive' : 'resistant'} sample ${libraries[index]}` })),
};

test('GSE336901-shaped raw CSV maps samples and groups without substituting data', async () => {
  const rows = [
    `gene,${libraries.join(',')}`,
    `ENSG0001,${libraries.map((_, index) => index + 1).join(',')}`,
    `ENSG0002,${libraries.map((_, index) => index + 3).join(',')}`,
  ].join('\n');
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(gzipSync(rows), { status: 200 });
  try {
    const result = await prepareGeoCounts(record, 'GSE336901_Fig3_FFPE_raw_counts_matrix_GEO.csv.gz');
    assert.equal(result.genes, 2);
    assert.deepEqual(result.columns.map(column => column.sample), sampleIds);
    assert.deepEqual(result.columns.map(column => column.condition), [...Array(5).fill('sensitive'), ...Array(5).fill('resistant')]);
    assert.match(await result.counts.text(), /^gene\tGZ23094742\t/);
    assert.match(await result.counts.text(), /ENSG0001\t1\t2\t3/);
  } finally { globalThis.fetch = original; }
});

test('normalized or fractional expression cannot enter DESeq2', async () => {
  const original = globalThis.fetch;
  globalThis.fetch = async () => new Response(gzipSync('gene,A,B\nENSG0001,1.4,2\nENSG0002,3,4\n'), { status: 200 });
  try {
    await assert.rejects(() => prepareGeoCounts(record, 'counts.csv.gz'), /non-integer or normalized/);
  } finally { globalThis.fetch = original; }
});
