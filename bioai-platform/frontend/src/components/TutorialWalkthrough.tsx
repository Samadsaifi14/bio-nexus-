'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, ChevronLeft, ChevronRight, BookOpen } from 'lucide-react';

const STEPS = [
  {
    title: 'Welcome to Bio Nexus',
    description: 'Bio Nexus is your all-in-one bioinformatics platform. From BLAST searches to protein structure visualization, everything is designed to be fast and intuitive. This short tour will show you the essentials.',
    highlight: 'sidebar',
  },
  {
    title: 'Running an analysis',
    description: 'Click any tool from the sidebar — BLAST, Alignment, Domain Analysis, and more. Paste a sequence, adjust parameters, and hit run. Results appear in seconds.',
    highlight: 'nav-analyze',
  },
  {
    title: 'Understanding results',
    description: 'Results are displayed with clean, interactive visualizations. Tables, graphs, and 3D viewers help you interpret your data at a glance. Each result can be downloaded or shared.',
    highlight: 'results',
  },
  {
    title: 'AI interpretation',
    description: 'Click "Interpret with AI" on any result page to get a plain-English explanation of what your results mean. The AI understands BLAST hits, pathway enrichment, domain architectures, and more.',
    highlight: 'ai',
  },
  {
    title: 'Learning more',
    description: 'Visit the Learn section for in-depth documentation on every concept — E-values, bootstrap values, pLDDT scores, and dozens more. Terms marked with a (?) icon have instant explanations.',
    highlight: 'nav-learn',
  },
];

const STORAGE_KEY = 'bio-nexus-onboarding';

export function TutorialWalkthrough() {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const seen = localStorage.getItem(STORAGE_KEY);
    if (!seen) {
      setVisible(true);
    }
  }, []);

  const dismiss = useCallback(() => {
    setVisible(false);
    localStorage.setItem(STORAGE_KEY, 'true');
  }, []);

  const next = useCallback(() => {
    if (step < STEPS.length - 1) {
      setStep(s => s + 1);
    } else {
      dismiss();
    }
  }, [step, dismiss]);

  const prev = useCallback(() => {
    if (step > 0) {
      setStep(s => s - 1);
    }
  }, []);

  const current = STEPS[step];

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          key="tutorial-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[200] flex items-center justify-center"
          style={{ background: 'rgba(4,4,10,0.75)', backdropFilter: 'blur(8px)' }}
        >
          <motion.div
            key={`step-${step}`}
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -16, scale: 0.97 }}
            transition={{ duration: 0.35, ease: [0.25, 1, 0.5, 1] }}
            className="relative w-full max-w-lg mx-4 p-8 rounded-2xl border border-glass-border shadow-glass-lg"
            style={{
              background: 'rgba(13,13,26,0.92)',
              backdropFilter: 'blur(32px) saturate(180%)',
            }}
          >
            <button
              onClick={dismiss}
              className="absolute top-4 right-4 p-1.5 rounded-lg text-text-muted hover:text-text-primary hover:bg-surface-1 transition"
              aria-label="Skip tutorial"
            >
              <X className="w-4 h-4" />
            </button>

            <div className="flex items-center gap-3 mb-6">
              <div className="p-2.5 rounded-xl bg-accent-cyan/10">
                <BookOpen className="w-5 h-5 text-accent-cyan" />
              </div>
              <div>
                <h2 className="text-lg font-semibold text-text-primary">{current.title}</h2>
                <p className="text-xs text-text-muted">Step {step + 1} of {STEPS.length}</p>
              </div>
            </div>

            <p className="text-sm text-text-secondary leading-relaxed mb-8">
              {current.description}
            </p>

            {/* Step dots */}
            <div className="flex items-center justify-center gap-1.5 mb-6">
              {STEPS.map((_, i) => (
                <div
                  key={i}
                  className={`h-1.5 rounded-full transition-all duration-300 ${
                    i === step
                      ? 'w-6 bg-accent-cyan'
                      : i < step
                        ? 'w-1.5 bg-accent-cyan/40'
                        : 'w-1.5 bg-glass-border'
                  }`}
                />
              ))}
            </div>

            <div className="flex items-center justify-between">
              <button
                onClick={prev}
                disabled={step === 0}
                className="btn-ghost px-4 py-2 text-sm disabled:opacity-30"
              >
                <ChevronLeft className="w-4 h-4" />
                Back
              </button>

              <div className="flex items-center gap-3">
                <button
                  onClick={dismiss}
                  className="text-xs text-text-muted hover:text-text-primary transition"
                >
                  Skip
                </button>

                <button
                  onClick={next}
                  className="btn-primary px-5 py-2 text-sm"
                >
                  {step < STEPS.length - 1 ? (
                    <>Next <ChevronRight className="w-4 h-4" /></>
                  ) : (
                    'Get Started'
                  )}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export function startTutorial() {
  localStorage.removeItem(STORAGE_KEY);
  window.location.reload();
}
