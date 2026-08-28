'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { CircleNotch as LoaderCircle, MagnifyingGlass as Search, Globe as Globe } from '@phosphor-icons/react';
import { fadeUp, stagger } from '@/lib/animations';
import { querySwissModel, type SwissModelResult } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { useAuditTrail } from '@/hooks/useAuditTrail';
import { DockingViewer } from '@/components/DockingViewer';
import { AIResultSummary } from '@/components/results/AIResultSummary';
import { BackButton, PageHeader, CriticalButton, FlatInput } from '@/components/ui';

export default function SwissModelPage() {
  const [accession, setAccession] = useState('');
  const [result, setResult] = useState<SwissModelResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'models' | 'experimental'>('models');
  const audit = useAuditTrail();

  const handleSearch = async () => {
    if (!accession.trim()) return;
    const acc = accession.trim().toUpperCase();
    audit.emitStarted('swissmodel_query', 'SWISS-MODEL', `acc:${acc}`);
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await querySwissModel(acc);
      setResult(res);
      audit.emitSuccess('swissmodel_query', 'SWISS-MODEL', `acc:${acc}`, `${res.models.length} models`);
    } catch (err: unknown) {
      const msg = extractErrorMessage(err, 'Query failed');
      audit.emitFailed('swissmodel_query', 'SWISS-MODEL', `acc:${acc}`, msg);
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const templates = activeTab === 'models' ? result?.models : result?.experimental;

  return (
    <div className="max-w-4xl">
      <BackButton />
      <PageHeader
        title="SWISS-MODEL Repository"
        subtitle="Query the SWISS-MODEL repository for homology models and experimental structures of a UniProt accession."
      />

      <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="data-card p-5 mb-6">
        <div className="flex gap-3">
          <FlatInput
            type="text"
            value={accession}
            onChange={(e) => { setAccession(e.target.value); setResult(null); setError(null); }}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="UniProt accession (e.g. P07900, P04637)"
            className="flex-1"
          />
          <CriticalButton onClick={handleSearch} disabled={loading || !accession.trim()}>
            {loading ? <LoaderCircle className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
            Search
          </CriticalButton>
        </div>

        <div className="flex gap-3 mt-3">
          {['P07900', 'P04637', 'P69905'].map((acc) => (
            <button
              key={acc}
              onClick={() => { setAccession(acc); setError(null); setResult(null); }}
              className="text-xs text-accent-cyan hover:text-accent-cyan/80 underline"
            >
              {acc}
            </button>
          ))}
        </div>
      </motion.div>

      {error && (
        <motion.div variants={fadeUp} initial={{ y: 24 }} animate="show" className="glass-card p-4 border border-error/20 mb-4">
          <p className="text-sm text-error">{error}</p>
        </motion.div>
      )}

      {result && (
        <motion.div variants={stagger} initial="hidden" animate="show" className="space-y-4">
          <AIResultSummary toolName="swissmodel" result={result as unknown as Record<string, unknown>} />
          <motion.div variants={fadeUp} className="data-card p-5">
            <div className="flex items-center justify-between mb-2">
              <h3 className="font-semibold text-text-primary">{result.accession}</h3>
              <a
                href={`https://www.uniprot.org/uniprotkb/${result.accession}`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-accent-cyan hover:underline flex items-center gap-1"
              >
                UniProt <Globe className="w-3 h-3" />
              </a>
            </div>
            {result.sequence && (
              <div className="mt-3">
                <p className="text-xs text-text-muted mb-1">Sequence ({result.sequence_length} residues)</p>
                <div className="font-mono text-xs bg-surface-0 p-3 rounded-lg break-all leading-relaxed max-h-24 overflow-y-auto text-text-secondary">
                  {result.sequence}
                </div>
              </div>
            )}
          </motion.div>

          <motion.div variants={fadeUp} className="data-card p-5">
            <div className="flex gap-4 mb-4 border-b border-glass-border">
              <button
                onClick={() => setActiveTab('models')}
                className={`pb-2 text-sm font-medium transition-colors ${
                  activeTab === 'models' ? 'text-accent-cyan border-b-2 border-accent-cyan' : 'text-text-muted hover:text-text-primary'
                }`}
              >
                Homology Models ({result.models.length})
              </button>
              <button
                onClick={() => setActiveTab('experimental')}
                className={`pb-2 text-sm font-medium transition-colors ${
                  activeTab === 'experimental' ? 'text-accent-cyan border-b-2 border-accent-cyan' : 'text-text-muted hover:text-text-primary'
                }`}
              >
                Experimental ({result.experimental.length})
              </button>
            </div>

            {!templates || templates.length === 0 ? (
              <p className="text-sm text-text-muted">No {activeTab === 'models' ? 'homology models' : 'experimental structures'} found.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-glass-border text-text-muted text-left text-xs">
                      <th className="pb-2 font-medium">Template</th>
                      <th className="pb-2 font-medium">Method</th>
                      <th className="pb-2 font-medium">Coverage</th>
                      <th className="pb-2 font-medium">State</th>
                      <th className="pb-2 font-medium">Date</th>
                      <th className="pb-2 font-medium"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {templates.map((t, i) => (
                      <tr key={i} className="border-b border-glass-border/50 hover:bg-surface-1 transition-colors">
                        <td className="py-2 font-mono text-xs text-accent-cyan">{t.template || '—'}</td>
                        <td className="py-2 text-xs">{t.method || '—'}</td>
                        <td className="py-2 text-xs">{t.coverage != null ? `${(t.coverage * 100).toFixed(0)}%` : '—'}</td>
                        <td className="py-2 text-xs">{t.oligo_state || '—'}</td>
                        <td className="py-2 text-xs">{t.created_date || '—'}</td>
                        <td className="py-2">
                          {t.coordinates_url && (
                            <a
                              href={t.coordinates_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-accent-cyan hover:underline"
                            >
                              PDB
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}
