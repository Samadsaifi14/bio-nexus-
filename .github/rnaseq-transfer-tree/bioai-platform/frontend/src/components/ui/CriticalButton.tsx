'use client';

import { CircleNotch as Loader2 } from '@phosphor-icons/react';

/**
 * Solid, deliberate action button for irreversible / expensive actions
 * (Run Pipeline, Submit Job, Delete). The hard flat shadow gives it real
 * weight so it never feels as casual to click as a clay toggle.
 */

interface CriticalButtonProps {
  children: React.ReactNode;
  onClick?: () => void;
  type?: 'button' | 'submit';
  disabled?: boolean;
  loading?: boolean;
  variant?: 'run' | 'danger' | 'submit';
  className?: string;
}

export function CriticalButton({
  children,
  onClick,
  type = 'button',
  disabled,
  loading,
  variant = 'run',
  className = '',
}: CriticalButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled || loading}
      className={`btn-critical ${variant === 'danger' ? 'btn-critical-danger' : ''} ${className}`}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}
