'use client';

import { motion } from 'framer-motion';
import { fadeUp } from '@/lib/animations';
import { CriticalButton, FlatTextarea } from '@/components/ui';

const SAMPLES = [
  {
    label: 'p53 (human)',
    seq: `>sp|P04637|P53_HUMAN Cellular tumor antigen p53
MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGP
DEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYPQGLNGTVNLPGRNSFEV
RVCACPHERCTEGRAVKLFSPKELNCEMAQDIINNKFNLNLLPETIPNTIICFVESQPPQGD
SVTTCFSWRGEGNEMYLHTEKEYKALKSTLSEKYMATCLLLSPKKKSLFPEALKLCNQKYS
EEFLLLDEALLSGCFAELACALHLAPAEGRYSGGFNHELYNMMTQQQQHQHHLQMQQHHQQ
HHQQHHQQHHQQQQQQQQQQQQQQQQQH`,
  },
  {
    label: 'Insulin (human)',
    seq: `>sp|P01308|INS_HUMAN Insulin
MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAED
LQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN`,
  },
];

interface SequenceInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
  error?: string | null;
}

export function SequenceInput({ value, onChange, onSubmit, loading, error }: SequenceInputProps) {
  const aaCount = value
    .split('\n')
    .filter((l) => !l.startsWith('>'))
    .join('').length;

  return (
    <motion.div variants={fadeUp} className="data-card p-6">
      <label className="block text-sm font-medium text-text-secondary mb-2">
        Enter protein sequence (FASTA or plain)
      </label>
      <FlatTextarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={10}
        placeholder={">sp|P04637|P53_HUMAN\nMEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQ..."}
      />
      {error && (
        <p className="mt-2 text-sm text-error">{error}</p>
      )}
      <div className="flex items-center justify-between mt-4">
        <div className="flex items-center gap-4">
          {SAMPLES.map((s) => (
            <button
              key={s.label}
              type="button"
              onClick={() => onChange(s.seq)}
              className="text-sm text-accent-cyan hover:underline underline-offset-2"
            >
              Load {s.label}
            </button>
          ))}
          <span className="text-xs text-text-muted">
            {value ? `${aaCount} aa` : '0 aa'}
          </span>
        </div>
        <CriticalButton
          onClick={onSubmit}
          disabled={!value.trim()}
          loading={loading}
          type="button"
        >
          {loading ? 'Running pipeline…' : 'Run Pipeline'}
        </CriticalButton>
      </div>
    </motion.div>
  );
}
