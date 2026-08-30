// ---------------------------------------------------------------------------
// Multi-assay NGS Platform (v2): assay router + QC contract engine + readiness gate
// ---------------------------------------------------------------------------

export type Ngs2Detection = {
  assay: string;
  sample_type: string;
  library_type: string;
  confidence: number;
  evidence: string[];
  pairs: string[][];
};

export type Ngs2StageContract = {
  step: string;
  tool: string;
  inputs: string[];
  outputs: string[];
  fail_blocks: boolean;
  expectation: string;
};

export type Ngs2Metric = {
  name: string;
  value: number | string | null;
  status: string;
  expected: string | null;
  detail: string | null;
};

export type Ngs2Stage = {
  step: string;
  tool: string;
  version: string;
  inputs: string[];
  outputs: string[];
  qc: {
    status: string;
    decision: string;
    metrics: Ngs2Metric[];
  } | null;
  decision: string;
  data: Record<string, unknown>;
};

type LegacyNgs2Stage = Omit<Ngs2Stage, 'inputs' | 'outputs' | 'qc'> & {
  inputs?: string[];
  outputs?: string[];
  input?: string[];
  output?: string[];
  qc?: { status?: string; decision?: string; metrics?: Ngs2Metric[] } | null;
};

function normalizeNgs2Stage(stage: LegacyNgs2Stage): Ngs2Stage {
  const qc = stage.qc ? {
    status: stage.qc.status ?? 'NOT_REPORTED',
    decision: stage.qc.decision ?? stage.decision ?? '—',
    metrics: Array.isArray(stage.qc.metrics) ? stage.qc.metrics : [],
  } : null;
  return {
    ...stage,
    step: stage.step ?? 'unnamed_stage',
    tool: stage.tool ?? 'not reported',
    version: stage.version ?? '',
    decision: stage.decision ?? qc?.decision ?? '—',
    data: stage.data && typeof stage.data === 'object' ? stage.data : {},
    inputs: Array.isArray(stage.inputs) ? stage.inputs : Array.isArray(stage.input) ? stage.input : [],
    outputs: Array.isArray(stage.outputs) ? stage.outputs : Array.isArray(stage.output) ? stage.output : [],
    qc,
  };
}

export type Ngs2AnalyzeResult = {
  detection: Ngs2Detection;
  requested: {
    assay: string;
    reference: string;
    synthetic_reference: boolean;
    demo_profile?: string | null;
    reads_loaded: Record<string, number>;
    reads_analyzed?: number;
  };
  demo?: { profile: string; label: string; description: string; synthetic: boolean; read_pairs: number } | null;
  pipeline: {
    pipeline: string;
    pipeline_status: string;
    pipeline_decision: string;
    stopped_at: string | null;
    warnings: string[];
    stages: Ngs2Stage[];
    provenance: Record<string, unknown>;
  };
  visualization: Ngs2Visualization;
};

export type Ngs2Visualization = {
  sam: string;
  vcf: string;
  locus: string | null;
  n_reads: number;
  n_mapped: number;
  n_variants: number;
};

export async function runNgs2Analyze(payload: {
  file_paths: string[];
  reference?: string;
  assay?: string;
  sample_type?: string;
  metadata?: Record<string, unknown>;
  synthetic_reference?: boolean;
  demo_profile?: string;
}): Promise<Ngs2AnalyzeResult> {
  const res = await longApi.post('/api/ngs/v2/analyze', payload);
  const raw = (res.data ?? {}) as Ngs2AnalyzeResult & { pipeline?: Ngs2AnalyzeResult['pipeline'] & { stages?: LegacyNgs2Stage[] } };
  const pipeline = raw.pipeline ?? { pipeline: 'unknown', pipeline_status: 'FAIL', pipeline_decision: 'STOP', stopped_at: null, warnings: ['Pipeline response missing'], stages: [], provenance: {} };
  return {
    ...raw,
    detection: raw.detection ?? { assay: 'UNKNOWN', sample_type: 'unknown', library_type: 'unknown', confidence: 0, evidence: [], pairs: [] },
    requested: raw.requested ?? { assay: 'UNKNOWN', reference: 'unknown', synthetic_reference: false, reads_loaded: {} },
    pipeline: {
      ...pipeline,
      warnings: Array.isArray(pipeline.warnings) ? pipeline.warnings : [],
      stages: Array.isArray(pipeline.stages) ? pipeline.stages.map(normalizeNgs2Stage) : [],
      provenance: pipeline.provenance && typeof pipeline.provenance === 'object' ? pipeline.provenance : {},
    },
    visualization: raw.visualization ?? { sam: '', vcf: '', locus: null, n_reads: 0, n_mapped: 0, n_variants: 0 },
  };
}

export async function listNgs2Stages(): Promise<Ngs2StageContract[]> {
  const res = await api.get('/api/ngs/v2/stages');
  return res.data.stages || [];
}

export async function detectNgs2Assay(payload: {
  file_paths: string[];
  reference?: string;
  assay?: string;
  metadata?: Record<string, unknown>;
}): Promise<Ngs2Detection> {
  const res = await api.post('/api/ngs/v2/detect', payload);
  return res.data;
}

// ---------------------------------------------------------------------------
// Staged Molecular Dynamics (v2): in-process MD DAG + QC contract engine
// ---------------------------------------------------------------------------

export type Md2Metric = {
  name: string;
  value: number | null;
  status: string;
  expected: string | null;
  detail: string | null;
};

export type Md2Stage = {
  step: string;
  tool: string;
  version: string;
  inputs: string[];
  outputs: string[];
  qc: {
    status: string;
    decision: string;
    metrics: Md2Metric[];
  } | null;
  decision: string;
  data: Record<string, unknown>;
};

export type Md2EngineStatus = {
  primary: string;
  engines: Record<string, { available: boolean; version?: string; note?: string }>;
};

export type Md2StageContract = {
  step: string;
  tool: string;
  inputs: string[];
  outputs: string[];
  fail_blocks: boolean;
  expectation: string;
};

export type Md2AnalyzeResult = {
  requested: {
    pdb_id: string;
    forcefield: string;
    solvent: string;
    production_ps: number | null;
    source: string;
  };
  pipeline: {
    pipeline: string;
    pipeline_status: string;
    pipeline_decision: string;
    stopped_at: string | null;
    warnings: string[];
    stages: Md2Stage[];
    provenance: Record<string, unknown>;
  };
};

export async function runMd2Analyze(payload: {
  pdb_id: string;
  forcefield?: string;
  solvent?: string;
  production_ps?: number;
  nvt_ps?: number;
}): Promise<Md2AnalyzeResult> {
  const res = await longApi.post('/api/md/v2/analyze', payload);
  return res.data;
}

export async function listMd2Stages(): Promise<Md2StageContract[]> {
  const res = await api.get('/api/md/v2/stages');
  return res.data.stages || [];
}

export async function getMd2EngineStatus(): Promise<Md2EngineStatus> {
  const res = await api.get('/api/md/v2/engine');
  return res.data;
}
