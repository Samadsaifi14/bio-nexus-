'use client';

import { useState } from 'react';

const SAMPLE = `>sp|P04637|P53_HUMAN Cellular tumor antigen p53
MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGP
DEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQKTYPQGLNGTVNLPGRNSFEV
RVCACPHERCTEGRAVKLFSPKELNCEMAQDIINNKFNLNLLPETIPNTIICFVESQPPQGD
SVTTCFSWRGEGNEMYLHTEKEYKALKSTLSEKYMATCLLLSPKKKSLFPEALKLCNQKYS
EEFLLLDEALLSGCFAELACALHLAPAEGRYSGGFNHELYNMMTQQQQHQHHLQMQQHHQQ
HHQQHHQQHHQQQQQQQQQQQQQQQQQH`;

interface SequenceInputProps {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  loading: boolean;
}

export default function SequenceInput({ value, onChange, onSubmit, loading }: SequenceInputProps) {
  const aaCount = value
    .split('\n')
    .filter((l) => !l.startsWith('>'))
    .join('').length;

  return (
    <div className="bg-white rounded-2xl border border-gray-200 p-6">
      <label className="block text-sm font-medium text-gray-700 mb-2">
        Enter protein sequence (FASTA or plain)
      </label>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder=">sp|P04637|P53_HUMAN&#10;MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQ..."
        className="w-full h-40 px-4 py-3 rounded-xl border border-gray-300 focus:border-green-500 focus:ring-2 focus:ring-green-200 outline-none transition font-mono text-sm text-gray-900 resize-none"
      />
      <div className="flex items-center justify-between mt-4">
        <div className="flex items-center gap-4">
          <button
            type="button"
            onClick={() => onChange(SAMPLE)}
            className="text-sm text-green-600 hover:text-green-700 underline"
          >
            Load sample (p53)
          </button>
          <span className="text-xs text-gray-400">
            {value ? `${aaCount} aa` : '0 aa'}
          </span>
        </div>
        <button
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          className="px-6 py-2.5 bg-green-600 text-white font-medium rounded-xl hover:bg-green-700 transition disabled:opacity-50"
        >
          {loading ? 'Running pipeline...' : 'Run Pipeline'}
        </button>
      </div>
    </div>
  );
}
