'use client';

import { useState, useRef, useEffect } from 'react';
import Link from 'next/link';
import { HelpCircle } from 'lucide-react';

interface LearnPopoverProps {
  term: string;
  explanation: string;
  topic?: string;
  children: React.ReactNode;
}

export function LearnPopover({ term, explanation, topic, children }: LearnPopoverProps) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <span ref={wrapperRef} className="inline-flex items-center gap-0.5 relative">
      <span
        className="cursor-pointer border-b border-dotted border-accent-cyan/40 hover:border-accent-cyan transition"
        onClick={() => setOpen(!open)}
        role="button"
        tabIndex={0}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setOpen(!open); } }}
        aria-label={`Learn about ${term}`}
      >
        {children}
      </span>
      <HelpCircle
        size={12}
        className="inline-block text-text-muted cursor-pointer hover:text-accent-cyan transition flex-shrink-0"
        onClick={() => setOpen(!open)}
      />
      {open && (
        <div
          className="absolute z-50 top-full left-0 mt-2 p-4 rounded-xl border border-glass-border bg-surface-2 shadow-glass-md max-w-xs text-sm"
          style={{ backdropFilter: 'blur(16px)' }}
        >
          <p className="font-semibold text-text-primary text-xs mb-1">{term}</p>
          <p className="text-text-secondary text-xs leading-relaxed">{explanation}</p>
          {topic && (
            <Link
              href={`/learn/${topic}`}
              className="inline-block mt-2 text-xs text-accent-cyan hover:underline font-medium"
            >
              Learn more &rarr;
            </Link>
          )}
        </div>
      )}
    </span>
  );
}
