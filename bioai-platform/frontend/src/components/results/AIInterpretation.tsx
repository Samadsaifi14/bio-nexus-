'use client';

import { useState, useRef, useCallback } from 'react';
import { Brain, Loader2 } from 'lucide-react';
import type { AssembledContext } from '@/types/pipeline';
import type { StreamEvent } from '@/types/results';
import { interpretStream } from '@/lib/api';
import { extractErrorMessage } from '@/lib/errors';

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
      <a key={match.index} href={match[2]} target="_blank" rel="noopener noreferrer" className="text-teal-600 hover:text-teal-700 underline">{match[1]}</a>
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
      elements.push(<h3 key={i} className="text-sm font-semibold text-gray-900 mt-4 mb-2">{line.slice(3)}</h3>);
    } else if (line.startsWith('- ')) {
      listItems.push(<li key={i} className="text-sm text-gray-700">{renderInlineMarkdown(line.slice(2))}</li>);
    } else if (line.match(/^\d+\.\s/)) {
      flushList();
      elements.push(<p key={i} className="text-sm text-gray-700 mb-1">{renderInlineMarkdown(line)}</p>);
    } else if (line.trim() === '') {
      flushList();
    } else {
      flushList();
      elements.push(<p key={i} className="text-sm text-gray-700 mb-2">{renderInlineMarkdown(line)}</p>);
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
    <div className="bg-gradient-to-br from-teal-50 to-teal-50 rounded-2xl border border-teal-200 p-6">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Brain className="w-5 h-5 text-teal-600" />
          <h2 className="font-semibold text-gray-900">AI Interpretation</h2>
          {model && model !== 'fallback-static' && (
            <span className="text-xs bg-teal-100 text-teal-700 px-2 py-0.5 rounded-full font-medium">
              Llama 3.3 70B
            </span>
          )}
        </div>
        {!text && !loading && (
          <button onClick={handleInterpret} className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 transition">
            Interpret results
          </button>
        )}
        {loading && (
          <button onClick={() => abortRef.current?.abort()} className="px-4 py-2 bg-gray-200 text-gray-700 text-sm font-medium rounded-lg hover:bg-gray-300 transition">
            Stop
          </button>
        )}
      </div>

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 mb-4">
          <p className="text-sm text-amber-800">{error}</p>
        </div>
      )}

      {text ? (
        <div>
          {renderMarkdown(text)}
          {model && <div className="mt-3 text-xs text-gray-400">Model: {model}</div>}
        </div>
      ) : loading ? (
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <Loader2 className="w-4 h-4 animate-spin" />
          Interpreting results...
        </div>
      ) : (
        <p className="text-sm text-gray-500">Click to get an AI explanation combining BLAST, UniProt, and AlphaFold data</p>
      )}
    </div>
  );
}
