'use client';

/**
 * Flat, near-opaque card for scientific output (charts, trees, scores).
 * No blur, no tint, no extrusion — translucency hurts data readability.
 */

interface DataCardProps {
  title?: string;
  subtitle?: string;
  actions?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

export function DataCard({ title, subtitle, actions, children, className = '' }: DataCardProps) {
  return (
    <section className={`data-card p-5 ${className}`}>
      {(title || actions) && (
        <header className="mb-4 flex items-center justify-between gap-3">
          <div>
            {title && (
              <h2 className="text-base font-semibold tracking-tight text-text-primary">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-0.5 text-xs text-text-muted">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      {children}
    </section>
  );
}
