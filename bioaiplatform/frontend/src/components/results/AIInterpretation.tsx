'use client';

import { useState, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import { Brain, LoaderCircle } from 'lucide-react';
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
      <a key={match.index} href={match[2]} target="_blank" rel="noopener noreferrer" className="text-accent-cyan hover:text-accent-cyan/80 underline">{match[1]}</a>
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
  const [text, setText] = useState('');
  const [model, setModel] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleInterpret = useCallback(async () => {
    if (loading) return;
    if (abortRef.current) abortRef.current.abort();

    setLoading(true);
    setText('');
    setModel('');
    setError(null);

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
                if (payload.error) {
                  setError(payload.error);
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
    <motion.div variants={fadeUp} whileHover={cardHover} className="glass-card p-6">
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
          <motion.button variants={fadeIn} onClick={handleInterpret} className="btn-primary px-4 py-2 text-sm">
            Interpret results
          </motion.button>
        )}
        {loading && (
          <button onClick={() => abortRef.current?.abort()} className="glass-card px-4 py-2 text-sm text-text-secondary hover:bg-surface-2 transition">
            Stop
          </button>
        )}
      </div>

      {error && (
        <div className="glass p-4 mb-4 border border-accent-amber/20">
          <p className="text-sm text-accent-amber">{error}</p>
        </div>
      )}

      {text ? (
        <motion.div variants={fadeIn}>
          {renderMarkdown(text)}
          {model && <div className="mt-3 text-xs text-text-muted">Model: {model}</div>}
        </motion.div>
      ) : loading ? (
        <div className="flex items-center gap-2 text-sm text-text-secondary">
          <LoaderCircle className="w-4 h-4 animate-spin" />
          Interpreting results...
        </div>
      ) : (
        <p className="text-sm text-text-secondary">Click to get an AI explanation combining BLAST, UniProt, and AlphaFold data</p>
      )}
    </motion.div>
  );
}
