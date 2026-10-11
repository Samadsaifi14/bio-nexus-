'use client';

import { useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { ArrowUpRight, Pause, Play } from '@phosphor-icons/react';
import type { SceneControl } from './ResearchCanvas';

const ResearchCanvas = dynamic(() => import('./ResearchCanvas'), { ssr: false });
const SplineCanvas = dynamic(() => import('./SplineCanvas'), { ssr: false });
const sceneUrl = process.env.NEXT_PUBLIC_SPLINE_SCENE_URL;

const chapters = [
  { id: 'biological-input', label: 'Biological input', title: 'Begin with a better question.', description: 'Bring sequences, structures or sequencing data. Choose a method that fits the question and the available evidence.', link: '/wizard', action: 'Find your workflow' },
  { id: 'scientific-analysis', label: 'Scientific analysis', title: 'Follow the molecular story.', description: 'Explore sequence similarity, molecular structure and simulation. Keep preparation, parameters and method limits in view.', link: '/analyze', action: 'Explore the methods' },
  { id: 'interpretable-evidence', label: 'Interpretable evidence', title: 'See how the answer was made.', description: 'Read results alongside their quality checks and provenance. Distinguish measured values, model estimates and interpretation.', link: '#principles', action: 'Read our approach' },
];

export function ImmersiveStory() {
  const root = useRef<HTMLElement>(null);
  const controller = useRef<SceneControl | null>(null);
  const progressRef = useRef(0);
  const [paused, setPaused] = useState(false);
  useEffect(() => {
    const element = root.current;
    if (!element) return;
    let cancelled = false;
    let cleanup: (() => void) | undefined;
    const start = async () => {
      const [{ gsap }, { ScrollTrigger }] = await Promise.all([import('gsap'), import('gsap/ScrollTrigger')]);
      if (cancelled) return;
      gsap.registerPlugin(ScrollTrigger);
      const media = gsap.matchMedia();
      media.add('(prefers-reduced-motion: no-preference)', () => {
        if (paused) return;
        gsap.from(element.querySelectorAll('[data-hero-word]'), { yPercent: 105, opacity: 0, stagger: .065, duration: .85, ease: 'power3.out' });
        element.querySelectorAll('[data-story-copy]').forEach(copy => {
          gsap.from(copy, { y: 30, opacity: .25, duration: .75, ease: 'power2.out', scrollTrigger: { trigger: copy, start: 'top 88%', once: true } });
        });
        const progress = { value: 0 };
        gsap.to(progress, { value: 1, ease: 'none', scrollTrigger: {
          trigger: element.querySelector('.bn-story-chapters'), start: 'top 65%', end: 'bottom 85%', scrub: .65,
        }, onUpdate: () => { progressRef.current = progress.value; controller.current?.setProgress(progress.value); } });
      }, element);
      cleanup = () => media.revert();
    };
    void start().catch(() => { /* Content is visible before animation initializes. */ });
    return () => { cancelled = true; cleanup?.(); };
  }, [paused]);

  return <section ref={root} className="bn-immersive" data-motion={paused ? 'paused' : 'active'} aria-label="The BioNexus research journey">
    <div className="bn-story-layout">
      <div className="bn-story-content">
        <div className="bn-story-intro">
          <p className="bn-story-eyebrow">Sequence. Structure. Understanding.</p>
          <h1 className="bn-story-title"><span className="bn-word-mask"><span data-hero-word>Biology,</span></span><br /><span className="bn-word-mask"><span data-hero-word>in perspective.</span></span></h1>
          <p className="bn-story-description">Explore biological questions with connected methods, visible quality checks and traceable results.</p>
          <Link href="/analyze" className="bn-button bn-button-primary">Enter the research workspace <ArrowUpRight size={19} aria-hidden="true" /></Link>
        </div>
        <div className="bn-story-chapters">
          {chapters.map(chapter => <article key={chapter.id} id={chapter.id} className="bn-story-chapter">
            <div data-story-copy>
              <p className="bn-chapter-label">{chapter.label}</p>
              <h2>{chapter.title}</h2>
              <p>{chapter.description}</p>
              <Link href={chapter.link} className="bn-text-link">{chapter.action} <ArrowUpRight size={18} aria-hidden="true" /></Link>
            </div>
          </article>)}
        </div>
      </div>
      <figure className="bn-story-visual">
        <div className="bn-story-stage">
          {/* A real raster poster keeps the first paint and non-WebGL experience useful. */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img className="bn-scene-poster" src="/scenes/research-poster.png" width="900" height="1050" alt="Illustrative sage-green double helix. The interactive scene transitions into molecular and evidence forms." fetchPriority="high" />
          {!paused && (sceneUrl ? <SplineCanvas url={sceneUrl} controller={controller} progressRef={progressRef} /> : <ResearchCanvas controller={controller} progressRef={progressRef} />)}
        </div>
        <figcaption>Conceptual molecular forms · Illustration, not analysis data</figcaption>
        <button type="button" className="bn-motion-toggle" onClick={() => setPaused(value => !value)} aria-pressed={paused}>
          {paused ? <Play size={15} aria-hidden="true" /> : <Pause size={15} aria-hidden="true" />}{paused ? 'Enable motion' : 'Pause motion'}
        </button>
      </figure>
    </div>
  </section>;
}
