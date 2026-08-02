'use client';

/**
 * Standard tool-page header — a title, a muted subtitle, and optional
 * trailing actions. Keeps the intro block identical across every analyze
 * page so the app reads as one system, not a set of hand-rolled headers.
 */

interface PageHeaderProps {
  title: string;
  subtitle?: string;
  actions?: React.ReactNode;
  className?: string;
}

export function PageHeader({ title, subtitle, actions, className = '' }: PageHeaderProps) {
  return (
    <header className={`mb-8 flex flex-wrap items-start justify-between gap-3 ${className}`}>
      <div>
        <h1 className="text-2xl font-bold text-text-primary">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-text-secondary">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 flex-shrink-0">{actions}</div>}
    </header>
  );
}
