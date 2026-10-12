'use client';

import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { ArrowUpRight } from '@phosphor-icons/react';

/** Shared across every research route; animations target introductions, never result surfaces. */
export function WorkspaceExperience() {
  const pathname = usePathname();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    void import('gsap').then(({ gsap }) => {
      if (cancelled || !ref.current) return;
      const media = gsap.matchMedia();
      media.add('(prefers-reduced-motion: no-preference)', () => {
        gsap.from(ref.current, { opacity: 0, y: 8, duration: .45, ease: 'power2.out' });
      });
      cleanup = () => media.revert();
    }).catch(() => {});
    return () => { cancelled = true; cleanup?.(); };
  }, [pathname]);
  const structural = /docking|structure|md|castp|swissmodel|admet|interactions/.test(pathname);
  const results = /results|report|history|jobs/.test(pathname);
  const label = results ? 'Return to the evidence.' : structural ? 'Explore the molecular perspective.' : 'Follow your biological question.';
  return <div ref={ref} className="bn-workspace-experience">
    <div className="bn-workspace-art" aria-hidden="true" />
    <div><p>{label}</p><span>Input, method and interpretation in one research workspace.</span></div>
    <Link href="/#biological-input" aria-label="Explore the BioNexus research story">The research journey <ArrowUpRight size={17} aria-hidden="true" /></Link>
  </div>;
}
