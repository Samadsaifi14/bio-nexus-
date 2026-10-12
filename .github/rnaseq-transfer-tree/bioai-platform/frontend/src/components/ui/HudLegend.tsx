'use client';

/**
 * Near-opaque, corner-anchored legend for 3D viewer overlays
 * (pLDDT key, interaction color key). Small, minimal, never obscuring
 * the model.
 */

interface HudLegendProps {
  title?: string;
  children: React.ReactNode;
  className?: string;
}

export function HudLegend({ title, children, className = '' }: HudLegendProps) {
  return (
    <div className={`hud-legend px-3 py-2 ${className}`}>
      {title && (
        <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wider text-text-muted">
          {title}
        </p>
      )}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">{children}</div>
    </div>
  );
}

export function LegendItem({
  color,
  label,
}: {
  color: string;
  label: string;
}) {
  return (
    <span className="flex items-center gap-1.5 text-[11px] text-text-secondary">
      <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm" style={{ backgroundColor: color }} />
      {label}
    </span>
  );
}
