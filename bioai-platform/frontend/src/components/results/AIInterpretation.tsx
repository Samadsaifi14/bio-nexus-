'use client';

import { useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Brain, CircleNotch as Loader2, Dna, MagnifyingGlass as Search } from '@phosphor-icons/react';
import type { AssembledContext } from '@/types/pipeline';
import type { StreamEvent } from '@/types/results';
import { interpretStream } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';
import { fadeUp, fadeIn, cardHover } from '@/lib/animations';

function addCitationLinks(text: string): string {
  return text.replace(
    /\b([A-Z][0-9][A-Z0-9]{3,})\b/g,
    (match) => {
      if (match.length < 5 || /^[A-Z]{5,}$/.test(match)) return match;
      return `[${match}](https://www.ncbi.nlm.nih.gov/protein/${match})`;
    }
  );
}

function renderInlineMarkdown(text: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) parts.push(text.slice(lastIndex, match.index));
    parts.push(
      <a key={match.index} href={match[2]} target="_blank" rel="noopener noreferrer" className="text-accent-cyan hover:text-accent-cyan underline">{match[1]}</a>
    );
    lastIndex = regex.lastIndex;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts.length === 1 ? parts[0] : <>{parts}</>;
}

function renderMarkdown(text: string) {
  const linked = addCitationLinks(text);
  const lines = linked.split('\n');
  const elements: React.ReactNode[] = [];
  let listItems: React.ReactNode[] = [];
  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(<ul key={`list-${elements.length}`} className="list-disc pl-5 space-y-1 mb-3">{listItems}</ul>);
      listItems = [];
    }
  };
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith('## ')) {
      flushList();
      elements.push(<h3 key={i} className="text-sm font-semibold text-text-primary mt-4 mb-2">{line.slice(3)}</h3>);
    } else if (line.startsWith('- ')) {
      listItems.push(<li key={i} className="text-sm text-text-secondary">{renderInlineMarkdown(line.slice(2))}</li>);
    } else if (line.match(/^\d+\.\s/)) {
      flushList();
      elements.push(<p key={i} className="text-sm text-text-secondary mb-1">{renderInlineMarkdown(line)}</p>);
    } else if (line.trim() === '') {
      flushList();
    } else {
      flushList();
      elements.push(<p key={i} className="text-sm text-text-secondary mb-2">{renderInlineMarkdown(line)}</p>);
    }
  }
  flushList();
  return elements;
}

interface AIInterpretationProps {
  context: AssembledContext;
  pipelineType: string;
}

export function AIInterpretation({ context, pipelineType }: AIInterpretationProps) {
  const router = useRouter();
  const [text, setText] = useState('');
  const [model, setModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleInterpret = useCallback(async () => {
    if (loading) return;
    if (abortRef.current) abortRef.current.abort();

    setLoading(true);
    setText('');
    setModel('');
    setError(null);
    setNotice(null);

    try {
      const response = await interpretStream({ pipeline_type: pipelineType, context });

      if (!response.ok) throw new Error('Failed to start interpretation');

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let accumulated = '';

      if (reader) {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          const chunk = decoder.decode(value, { stream: true });
          for (const line of chunk.split('\n')) {
            if (line.startsWith('data: ')) {
              try {
                const payload: StreamEvent = JSON.parse(line.slice(6));
                if (payload.chunk) {
                  accumulated += payload.chunk;
                  setText(accumulated);
                }
                if (payload.done) {
                  setModel(payload.meta?.model || '');
                }
                if (payload.notice) {
                  setNotice(payload.notice);
                }
                if (payload.error) {
                  const msg = payload.error.includes('organization_restricted')
                    ? 'AI interpretation is temporarily unavailable due to a provider restriction. Please try again later.'
                    : payload.error;
                  setError(msg);
                }
              } catch {}
            }
          }
        }
      }
    } catch (err: unknown) {
      if (!(err instanceof Error) || err.name !== 'AbortError') {
        setError(extractErrorMessage(err, 'Interpretation failed'));
      }
    } finally {
      setLoading(false);
    }
  }, [context, pipelineType, loading]);

  return (
    <motion.div variants={fadeUp} whileHover={cardHover} className="bg-accent-cyan/[0.06] rounded-2xl border border-accent-cyan/20 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-accent-cyan" />
          <h2 className="font-semibold text-text-primary">AI Interpretation</h2>
          {model && model !== 'fallback-static' && (
            <span className="text-xs bg-accent-cyan/10 text-accent-cyan px-2 py-0.5 rounded-full font-medium">
              Llama 3.3 70B
            </span>
          )}
        </div>
        {!text && !loading && (
          <motion.button variants={fadeIn} onClick={handleInterpret} className="px-4 py-2 bg-accent-cyan text-void text-sm font-medium rounded-lg hover:bg-accent-hover transition">
            {error ? 'Retry' : 'Interpret results'}
          </motion.button>
        )}
        {loading && (
          <button onClick={() => abortRef.current?.abort()} className="px-4 py-2 bg-surface-2 text-text-secondary text-sm font-medium rounded-lg hover:bg-surface-3 transition">
            Stop
          </button>
        )}
      </div>

      {error && !loading && (
        <div className="bg-error/10 border border-error/30 rounded-xl p-4 mb-4">
          <p className="text-sm text-error">{error}</p>
        </div>
      )}

      {loading && notice && (
        <div className="flex items-center gap-2 text-xs text-accent-amber mb-3">
          <Loader2 className="w-3.5 h-3.5 animate-spin" />
          {notice}
        </div>
      )}

      {text ? (
        <motion.div variants={fadeIn}>
          {renderMarkdown(text)}
          {model && <div className="mt-3 text-xs text-text-muted">Model: {model}</div>}
          <div className="mt-4 pt-3 border-t border-accent-cyan/20 space-y-2">
            <div className="flex items-center gap-2 text-xs text-accent-cyan font-medium mb-2">Bridges</div>
            <div className="flex flex-wrap gap-2">
              <button onClick={() => router.push('/analyze/primers')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-cyan text-void text-xs font-medium hover:bg-accent-hover transition">
                <Dna className="w-3.5 h-3.5" /> Design Primers (F4)
              </button>
              <button onClick={() => router.push('/analyze')}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-accent-cyan/10 text-accent-cyan text-xs font-medium hover:bg-accent-cyan/20 transition border border-accent-cyan/20">
                <Search className="w-3.5 h-3.5" /> Run New Analysis (F8)
              </button>
            </div>
          </div>
        </motion.div>
      ) : loading ? (
        <div className="flex items-center gap-2 text-sm text-text-muted">
          <Loader2 className="w-4 h-4 animate-spin" />
          Interpreting results...
        </div>
      ) : (
        <p className="text-sm text-text-muted">Click to get an AI explanation combining BLAST, UniProt, and AlphaFold data</p>
      )}
    </motion.div>
  );
}
