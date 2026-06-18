'use client';

import { useState, useEffect } from 'react';
import { Dna } from 'lucide-react';

const SEQUENCES = [
  {
    label: 'p53 tumor suppressor',
    seq: 'MEEPQSDPSVEPPLSQETFSDLWKLLPENNVLSPLPSQAMDDLMLSPDDIEQWFTEDPGPDEAPRMPEAAPPVAPAPAAPTPAAPAPAPSWPLSSSVPSQK',
  },
  {
    label: 'Insulin precursor',
    seq: 'MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN',
  },
  {
    label: 'BRCA1 (partial)',
    seq: 'MDLSALRVEEVQNVINAMQKILECPICLELIKEPVSTKCDHIFCKFCMLKLLNQKKGPSQCPLCKNDITKRSLQESTRFSQLVEELLKIICAFQLDTGLEYANSYNFAKKENN',
  },
];

export function SequenceTypewriter() {
  const [current, setCurrent] = useState(0);
  const [typing, setTyping] = useState(true);
  const [displayed, setDisplayed] = useState('');
  const [showCursor, setShowCursor] = useState(true);

  useEffect(() => {
    const seq = SEQUENCES[current].seq;
    if (!typing) return;

    let i = 0;
    const interval = setInterval(() => {
      i++;
      setDisplayed(seq.slice(0, i));
      if (i >= seq.length) {
        clearInterval(interval);
        setTyping(false);
        setTimeout(() => {
          setTyping(true);
          setCurrent((c) => (c + 1) % SEQUENCES.length);
        }, 3000);
      }
    }, 25);
    return () => clearInterval(interval);
  }, [current, typing]);

  return (
    <div className="bg-gray-900 rounded-2xl border border-gray-700 p-6 shadow-xl">
      <div className="flex items-center gap-2 mb-3">
        <Dna className="w-4 h-4 text-teal-400" />
        <span className="text-xs text-teal-400 font-medium font-mono uppercase tracking-wider">
          Query: {SEQUENCES[current].label}
        </span>
      </div>
      <div className="relative">
        <code className="font-mono text-sm leading-relaxed text-teal-300 break-all">
          {displayed}
          {showCursor && <span className="inline-block w-[2px] h-4 bg-teal-400 ml-0.5 animate-blink align-middle" />}
        </code>
      </div>
      <div className="mt-3 flex items-center gap-2 text-xs text-gray-500">
        <span className="inline-block w-2 h-2 rounded-full bg-teal-500 animate-pulse" />
        <span>Live sequence analysis ready — paste your own sequence above</span>
      </div>
    </div>
  );
}
