import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import ts from 'typescript';

async function load(name) {
  const code = ts.transpileModule(readFileSync(new URL('../src/lib/' + name, import.meta.url), 'utf8'),
    { compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 } }).outputText;
  return import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'));
}
const { readInterpretationEvents, safeInterpretationHref } = await load('interpretationStream.ts');
const { explainRnaSeqResult } = await load('rnaseqInterpretation.ts');

const payload = 'data: {"chunk":"β snow"}\r\n\r\ndata: {"notice":"retry"}\n\ndata: {"done":true,"meta":{"model":"actual/provider","pipeline_type":"rna"}}\n\n';
const bytes = new TextEncoder().encode(payload);
const response = new Response(new ReadableStream({
  start(controller) {
    for (const value of bytes) controller.enqueue(new Uint8Array([value]));
    controller.close();
  },
}));
const seen = [];
for await (const event of readInterpretationEvents(response)) seen.push(event);
assert.deepEqual(seen, [
  { chunk: 'β snow' }, { notice: 'retry' },
  { done: true, meta: { model: 'actual/provider', pipeline_type: 'rna' } },
]);
const multiple = [];
for await (const event of readInterpretationEvents(new Response(': heartbeat\n\ndata: {"chunk":\ndata: "multi"}\n\n'))) multiple.push(event);
assert.deepEqual(multiple, [{ chunk: 'multi' }]);
const last = [];
for await (const event of readInterpretationEvents(new Response('data: {"done":true}'))) last.push(event);
assert.deepEqual(last, [{ done: true }]);
await assert.rejects(async () => {
  for await (const event of readInterpretationEvents(new Response('data: {"chunk":42}\n\n'))) void event;
}, /Invalid interpretation/);
const controller = new AbortController();
controller.abort();
await assert.rejects(async () => {
  for await (const event of readInterpretationEvents(new Response(payload), controller.signal)) void event;
}, { name: 'AbortError' });
assert.equal(safeInterpretationHref('javascript:alert(1)'), null);
assert.equal(safeInterpretationHref('data:text/html,unsafe'), null);
assert.equal(safeInterpretationHref('https://example.org/evidence'), 'https://example.org/evidence');

const fixture = {
  state: 'SUCCEEDED', run_id: 'fixture', artifacts: [],
  summary: { test_level: 'SALS', reference_level: 'healthy', design: '~ batch + condition',
    samples: 18, genes_input: 22085, genes_kept: 20169, significant: 0, up: 0, down: 0,
    alpha: .05, lfc_threshold: 1, pca_percent_variance: { PC1: 15.317, PC2: 10.551 },
    normalization_method: 'median_of_ratios', design_full_rank: true,
    design_warnings: ['Review sample identity'], expression_heatmap_generated: true,
    expression_heatmap_basis: 'top_variable_genes_QC',
    enrichment: { status: 'NO_SIGNIFICANT_TERMS', method: 'Recorded ORA', coverage_warning: 'Low mapping coverage' } },
};
let report = explainRnaSeqResult(fixture);
assert.match(report.statements.find(x => x.title === 'Comparison and direction').text, /SALS with healthy as reference/);
assert.match(report.statements.find(x => x.title === 'Differential expression').text, /No genes met both/);
assert.match(report.statements.find(x => x.title === 'Heatmap meaning').text, /must not be described as significant/);
assert.match(report.statements.find(x => x.title === 'Functional enrichment').text, /does not prove absence/);
assert(report.caveats.includes('Review sample identity') && report.caveats.includes('Low mapping coverage'));
assert(report.statements.every(x => x.artifacts.length > 0));
report = explainRnaSeqResult({ ...fixture, summary: { ...fixture.summary,
  enrichment: { status: 'UNRESOLVED_ESTIMATES', method: 'GSEA' }, samples: NaN, design_full_rank: false } });
assert.match(report.statements.find(x => x.title === 'Counts and normalization').text, /not reported samples/);
assert.match(report.statements.find(x => x.title === 'Functional enrichment').text, /not evidence of no enrichment/);
assert.match(report.caveats[0], /identifiability is not confirmed/);
assert.equal(explainRnaSeqResult({ ...fixture, state: 'QC_READY' }).statements.length, 0);
const dockingPrototype = await load('../../../src/features/docking-validation.ts');
await assert.rejects(dockingPrototype.runDockingValidation('/not-a-molecule.apk'), /cannot validate molecular docking/);
const dockingPage = readFileSync(new URL('../src/app/(dashboard)/analyze/docking/page.tsx', import.meta.url), 'utf8');
assert(!dockingPage.includes('runDockingValidation') && !dockingPage.includes('APK Path'));
console.log('Interpretation streaming, RNA-seq evidence and APK/molecular boundary checks passed');

const { checkNumericGrounding } = await load('numericGrounding.ts');
const explanation = text => ({ headline: 'Recorded result', summary: text, findings: [], caveats: [] });
const ppi = { interactions: Array.from({ length: 12 }, () => ({ score: .99 })) };
assert.equal(checkNumericGrounding(explanation('There are 12 partners.'), ppi).grounded, true);
assert.equal(checkNumericGrounding(explanation('There are 13 partners.'), ppi).grounded, false);
assert.equal(checkNumericGrounding(explanation('There are 3 partners.'), { count: 1 }).grounded, false);
assert.equal(checkNumericGrounding(explanation('Score is 99.'), { score: .99 }).grounded, false);
assert.equal(checkNumericGrounding(explanation('Score is 0.99%.'), { score: .99 }).grounded, false);
assert.equal(checkNumericGrounding(explanation('Score is 7.'), { score: -7 }).grounded, false);
assert.equal(checkNumericGrounding(explanation('There are 42 partners.'), { ai_interpretation: { summary: '42' } }).grounded, false);

const { openDotPlot, consumeParam } = await load('cross-link.ts');
const storage = new Map();
globalThis.window = {};
globalThis.sessionStorage = { getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key) };
let target;
openDotPlot({ push: route => { target = route; } }, 'MPRIVATESEQ', 'MOTHERSEQ', 'blosum62');
assert.equal(target, '/analyze/dotplot');
assert.equal(target.includes('MPRIVATESEQ'), false);
assert.deepEqual(JSON.parse(consumeParam('dotplot_input')), {
  sequenceA: 'MPRIVATESEQ', sequenceB: 'MOTHERSEQ', scoring: 'blosum62', self: false });
assert.equal(consumeParam('dotplot_input'), null);
console.log('Numeric grounding and private sequence handoff checks passed.');
