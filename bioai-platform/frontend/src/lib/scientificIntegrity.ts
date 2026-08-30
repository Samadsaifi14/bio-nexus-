export type IntegrityIssue = { level: 'ERROR' | 'WARN'; code: string; message: string; stage?: string };

type MetricLike = { name?: string; value?: unknown; status?: string };
type StageLike = { step?: string; tool?: string; qc?: { status?: string; metrics?: MetricLike[] } | null; decision?: string };

export function validateScientificStages(stages: StageLike[]): IntegrityIssue[] {
  const issues: IntegrityIssue[] = [];
  const seenStages = new Set<string>();

  stages.forEach((stage, index) => {
    const step = String(stage?.step || '').trim();
    const stageName = step || `stage-${index + 1}`;
    if (!step) issues.push({ level: 'ERROR', code: 'MISSING_STAGE_ID', stage: stageName, message: `Stage ${index + 1} has no stable step identifier.` });
    if (step && seenStages.has(step)) issues.push({ level: 'ERROR', code: 'DUPLICATE_STAGE', stage: step, message: `Duplicate stage '${step}' was emitted.` });
    if (step) seenStages.add(step);
    if (!String(stage?.tool || '').trim()) issues.push({ level: 'WARN', code: 'MISSING_TOOL', stage: stageName, message: `Tool provenance is missing for ${stageName}.` });

    const qcStatus = stage?.qc?.status;
    if (qcStatus && !['PASS', 'WARN', 'FAIL'].includes(qcStatus)) issues.push({ level: 'ERROR', code: 'INVALID_QC_STATUS', stage: stageName, message: `Unsupported QC status '${qcStatus}'.` });

    const metrics = Array.isArray(stage?.qc?.metrics) ? stage.qc!.metrics! : [];
    const seenMetrics = new Set<string>();
    metrics.forEach((metric) => {
      const name = String(metric?.name || '').trim();
      if (!name) issues.push({ level: 'WARN', code: 'MISSING_METRIC_NAME', stage: stageName, message: `An unnamed metric was emitted by ${stageName}.` });
      if (name && seenMetrics.has(name)) issues.push({ level: 'ERROR', code: 'DUPLICATE_METRIC', stage: stageName, message: `Metric '${name}' is duplicated within ${stageName}.` });
      if (name) seenMetrics.add(name);
      if (typeof metric?.value === 'number' && !Number.isFinite(metric.value)) issues.push({ level: 'ERROR', code: 'NONFINITE_METRIC', stage: stageName, message: `Metric '${name || 'unnamed'}' has a non-finite numeric value.` });
      if (metric?.status && !['PASS', 'WARN', 'FAIL'].includes(metric.status)) issues.push({ level: 'ERROR', code: 'INVALID_METRIC_STATUS', stage: stageName, message: `Metric '${name || 'unnamed'}' has unsupported status '${metric.status}'.` });
    });
  });

  return issues;
}

export function uniqueByLabel<T extends { label: string }>(items: T[]): T[] {
  const seen = new Set<string>();
  return items.filter((item) => {
    const key = item.label.trim().toLowerCase();
    if (!key || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
