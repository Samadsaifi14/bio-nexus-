'use client';

import Link from 'next/link';
import { ArrowLeft } from 'lucide-react';

/**
 * Navigation affordance used at the top of tool pages to return to the
 * operation hub. Navigation chrome is "liquid-glass" territory — quiet
 * unless you reach for it, then it lights up.
 */

interface BackButtonProps {
  href?: string;
  label?: string;
  className?: string;
}

export function BackButton({ href = '/analyze', label = 'Choose a different operation', className = '' }: BackButtonProps) {
  return (
    <Link
      href={href}
      className={`group inline-flex items-center gap-1.5 text-sm text-text-muted hover:text-text-primary transition-colors mb-6 w-fit ${className}`}
    >
      <span className="inline-flex items-center gap-1 rounded-md px-1 py-0.5 -ml-1 transition-colors group-hover:text-accent-cyan">
        <ArrowLeft className="w-4 h-4 transition-transform group-hover:-translate-x-0.5" />
      </span>
      {label}
    </Link>
  );
}
