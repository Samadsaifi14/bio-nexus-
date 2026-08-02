'use client';

/**
 * Spatial HUD chrome — controls that sit at a fixed depth in the 3D
 * viewer's scene, near-opaque so the model underneath stays readable.
 * Never blurred glass over a structure people are trying to parse.
 */

interface HudPanelProps {
  children: React.ReactNode;
  className?: string;
}

export function HudPanel({ children, className = '' }: HudPanelProps) {
  return <div className={`hud ${className}`}>{children}</div>;
}
