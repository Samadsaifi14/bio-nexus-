'use client';

import type { ReactNode } from 'react';

type IconProps = { className?: string };

function SvgBase({ className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
    >
      {children}
    </svg>
  );
}

export function AlignmentBarIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <rect x="10" y="6" width="4" height="12" rx="1" fill="currentColor" opacity={0.16} stroke="none" />
      <path d="M4 8h16M4 12h16M4 16h16" />
      <circle cx="12" cy="8" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="12" r="1" fill="currentColor" stroke="none" />
      <circle cx="12" cy="16" r="1" fill="currentColor" stroke="none" />
    </SvgBase>
  );
}

export function HelixRibbonIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <path d="M12 3c-4 2.5-4 5 0 7.5s4 5 0 7.5" />
      <path d="M12 3c4 2.5 4 5 0 7.5s-4 5 0 7.5" />
    </SvgBase>
  );
}

export function DockingPocketIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <path d="M4 9c0 6 8 6 8 6s8 0 8-6" />
      <circle cx="12" cy="6.5" r="2.6" />
    </SvgBase>
  );
}

export function PhyloTIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <path d="M12 3v5M12 8H8M12 8h8" />
      <path d="M8 8v6H5M8 8v6h3M20 8v6h-3M20 8v6h3" />
      <circle cx="12" cy="8" r="1.1" fill="currentColor" stroke="none" />
    </SvgBase>
  );
}

export function EnrichmentClusterIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <circle cx="8.5" cy="8.5" r="1.9" />
      <circle cx="15.5" cy="8.5" r="1.9" />
      <circle cx="8.5" cy="15.5" r="1.9" />
      <circle cx="15.5" cy="15.5" r="1.9" />
      <circle cx="12" cy="12" r="4.6" strokeDasharray="2 2" opacity={0.5} />
      <circle cx="12" cy="12" r="2.1" fill="currentColor" stroke="none" />
    </SvgBase>
  );
}

export function ReadPileupIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <path d="M4 6h16M4 10h16M4 14h16M4 18h16" />
      <circle cx="9" cy="6" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="15" cy="10" r="1.2" fill="currentColor" stroke="none" />
      <circle cx="7" cy="14" r="1.2" fill="currentColor" stroke="none" />
    </SvgBase>
  );
}

export function PPIWebIcon({ className }: IconProps) {
  return (
    <SvgBase className={className}>
      <path d="M6 6h5M11 6l3 6M6 6l3 6M11 18l-3-6M11 18l3-6" />
      <circle cx="6" cy="6" r="1.9" />
      <circle cx="11" cy="6" r="1.9" />
      <circle cx="8" cy="12" r="1.9" />
      <circle cx="14" cy="12" r="1.9" />
      <circle cx="11" cy="18" r="1.9" />
    </SvgBase>
  );
}
