'use client';

/**
 * Glassmorphism container for transient, layered UI — job status, toasts,
 * panels floating over the 3D viewer. Communicates "temporary chrome,
 * not permanent data."
 */

interface GlassPanelProps {
  children: React.ReactNode;
  className?: string;
}

export function GlassPanel({ children, className = '' }: GlassPanelProps) {
  return <div className={`glass-panel rounded-xl ${className}`}>{children}</div>;
}
