'use client';

const SCRIPT_ID = 'bionexus-pdbe-molstar-script';
const STYLE_ID = 'bionexus-pdbe-molstar-style';
const SCRIPT_URL = 'https://cdn.jsdelivr.net/npm/pdbe-molstar@3.12.0/build/pdbe-molstar-component.js';
const STYLE_URL = 'https://cdn.jsdelivr.net/npm/pdbe-molstar@3.12.0/build/pdbe-molstar.css';

let loadPromise: Promise<void> | null = null;

function ensureStylesheet() {
  if (document.getElementById(STYLE_ID)) return;

  const link = document.createElement('link');
  link.id = STYLE_ID;
  link.rel = 'stylesheet';
  link.href = STYLE_URL;
  link.crossOrigin = 'anonymous';
  document.head.appendChild(link);
}

/**
 * Load the PDBe Mol* web component only on routes that actually render it.
 *
 * Keeping this out of the root layout prevents the landing page, RNA-seq,
 * BLAST and other non-structure routes from paying the download/parse cost of
 * a large third-party 3D viewer before they become interactive.
 */
export function ensurePdbeMolstar(): Promise<void> {
  if (typeof window === 'undefined') return Promise.resolve();

  ensureStylesheet();

  if (window.customElements?.get('pdbe-molstar')) {
    return Promise.resolve();
  }

  if (loadPromise) return loadPromise;

  loadPromise = new Promise<void>((resolve, reject) => {
    const finish = () => {
      window.customElements
        .whenDefined('pdbe-molstar')
        .then(() => resolve())
        .catch(reject);
    };

    const existing = document.getElementById(SCRIPT_ID) as HTMLScriptElement | null;
    if (existing) {
      if (window.customElements?.get('pdbe-molstar')) {
        resolve();
      } else {
        finish();
      }
      return;
    }

    const script = document.createElement('script');
    script.id = SCRIPT_ID;
    script.src = SCRIPT_URL;
    script.async = true;
    script.defer = true;
    script.crossOrigin = 'anonymous';
    script.addEventListener('load', finish, { once: true });
    script.addEventListener(
      'error',
      () => {
        loadPromise = null;
        reject(new Error('PDBe Mol* failed to load.'));
      },
      { once: true },
    );
    document.head.appendChild(script);
  });

  return loadPromise;
}
