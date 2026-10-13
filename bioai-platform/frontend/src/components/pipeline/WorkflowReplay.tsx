'use client';
import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import toast from 'react-hot-toast';
import { exportWorkflowRecipe, replayWorkflow, validateWorkflowRecipe, runWorkflowRecipe, runWorkflowCollection, WorkflowCollectionItem } from '@/lib/api';

export function WorkflowReplay({ jobId }: { jobId: string }) {
  const [sequence, setSequence] = useState('');
  const [collection, setCollection] = useState('');
  const [collectionItems, setCollectionItems] = useState<WorkflowCollectionItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [plan, setPlan] = useState<Record<string, unknown> | null>(null);
  const collectionSubmission = useRef<{ fingerprint: string; id: string } | null>(null);
  const router = useRouter();
  const busyRef = useRef(false);
  const planRevision = useRef(0);
  const activeJob = useRef(jobId);
  useEffect(() => {
    activeJob.current = jobId;
    planRevision.current += 1;
    setPlan(null);
    setSequence('');
    setCollection('');
    setCollectionItems([]);
    collectionSubmission.current = null;
    return () => { planRevision.current += 1; };
  }, [jobId]);
  useEffect(() => { collectionSubmission.current = null; }, [plan]);
  async function perform(action: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    try { await action(); } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Workflow action failed');
    } finally { busyRef.current = false; setBusy(false); }
  }
  return <section className="glass-card p-4 space-y-3">
    <h2 className="font-semibold text-text-primary">Replay a recorded workflow</h2>
    <p className="text-sm text-text-secondary">Export or validate a portable BioNexus recipe. Replay checks the original input checksum and queues a new private run using recorded steps and parameters. External databases may change; identical results are not guaranteed.</p>
    <div className="flex flex-wrap gap-3">
      <button disabled={busy} onClick={() => perform(async () => {
        const revision = ++planRevision.current;
        setPlan(null);
        const result = await exportWorkflowRecipe(jobId);
        if (revision !== planRevision.current || activeJob.current !== jobId) return;
        setPlan(result);
        const blob = new Blob([JSON.stringify(result.recipe, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a'); anchor.href = url; anchor.download = `workflow-recipe-${jobId}.json`; anchor.click(); URL.revokeObjectURL(url);
      })} className="text-sm underline disabled:opacity-50">Export recipe</button>
      <label className="text-sm underline cursor-pointer">Validate recipe JSON
        <input type="file" accept=".json,application/json" className="sr-only" disabled={busy} onChange={event => {
          const file = event.target.files?.[0];
          if (file) void perform(async () => {
            const revision = ++planRevision.current;
            setPlan(null);
            if (file.size > 100000) throw new Error('Recipe exceeds 100 KB');
            const result = await validateWorkflowRecipe(JSON.parse(await file.text()));
            if (revision === planRevision.current && activeJob.current === jobId) setPlan(result);
          }); event.target.value = '';
        }} />
      </label>
    </div>
    {plan && <p className="text-sm text-text-secondary">Recipe validated for the BioNexus worker. {Array.isArray(plan.steps) ? plan.steps.length : 0} planned steps; no tools launched by validation.</p>}
    <label className="block text-sm text-text-primary" htmlFor="workflow-replay-input">Sequence or FASTA (replay requires original input)</label>
    <textarea disabled={busy} id="workflow-replay-input" value={sequence} onChange={event => setSequence(event.target.value)} rows={3} className="w-full border border-border rounded p-2 bg-transparent" />
    {plan && <button disabled={busy || !sequence.trim()} onClick={() => perform(async () => {
      const result = await runWorkflowRecipe(plan.recipe, sequence);
      if (activeJob.current !== jobId) return;
      toast.success("Recipe run queued"); router.push(`/jobs/${result.job_id}`);
    })} className="text-sm px-3 py-2 border border-border rounded disabled:opacity-50">Queue validated recipe with this input</button>}
    <button disabled={busy || !sequence.trim()} onClick={() => perform(async () => {
      const result = await replayWorkflow(jobId, sequence);
      if (activeJob.current !== jobId) return;
      toast.success('Workflow queued'); router.push(`/jobs/${result.job_id}`);
    })} className="text-sm px-3 py-2 border border-border rounded disabled:opacity-50">{busy ? 'Working…' : 'Queue replay with original configuration'}</button>
    <div className="border-t border-border pt-3 space-y-2">
      <h3 className="font-medium">Run a protein collection</h3>
      <p className="text-sm text-text-secondary">Export this workflow or validate a recipe first, then provide 1–10 protein FASTA records with unique identifiers. Each creates a private queued job and uses one daily analysis. Queued status does not mean analysis is complete.</p>
      <label htmlFor="workflow-collection" className="block text-sm">Protein multi-FASTA</label>
      <textarea id="workflow-collection" disabled={busy} value={collection} onChange={event => { collectionSubmission.current = null; setCollection(event.target.value); setCollectionItems([]); }} rows={5} className="w-full border border-border rounded p-2 bg-transparent" />
      <button disabled={busy || !plan || !collection.trim()} onClick={() => perform(async () => {
        if (!plan) return;
        const fingerprint = JSON.stringify({ recipe: plan.recipe, collection });
        if (collectionSubmission.current?.fingerprint !== fingerprint) collectionSubmission.current = { fingerprint, id: crypto.randomUUID() };
        const result = await runWorkflowCollection(plan.recipe, collection, collectionSubmission.current.id);
        if (activeJob.current !== jobId) return;
        setCollectionItems(result.items);

        toast.success('Collection submission returned; inspect each item');
      })} className="text-sm px-3 py-2 border border-border rounded disabled:opacity-50">Queue collection with validated recipe</button>
      {collectionItems.length > 0 && <ul className="text-sm space-y-1" aria-live="polite">{collectionItems.map(item => <li key={item.identifier}>
        {item.identifier}: {item.status} {item.job_id && <a className="underline" href={`/jobs/${encodeURIComponent(item.job_id)}`}>Open job</a>} {item.error}
      </li>)}</ul>}
    </div>
  </section>;
}
