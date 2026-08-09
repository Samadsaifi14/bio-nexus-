import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        // All themed colors are CSS-variable RGB triplets so the same utility
        // resolves per active `data-theme` and opacity modifiers keep working.
        void: 'rgb(var(--bg-void) / <alpha-value>)',
        surface: {
          0: 'rgb(var(--bg-surface-0) / <alpha-value>)',
          1: 'rgb(var(--bg-surface-1) / <alpha-value>)',
          2: 'rgb(var(--bg-surface-2) / <alpha-value>)',
          3: 'rgb(var(--bg-surface-3) / <alpha-value>)',
        },
        'accent-cyan': 'rgb(var(--accent-cyan) / <alpha-value>)',
        'accent-hover': 'rgb(var(--accent-hover) / <alpha-value>)',
        'accent-purple': 'rgb(var(--accent-purple) / <alpha-value>)',
        'accent-amber': 'rgb(var(--accent-amber) / <alpha-value>)',
        'text-primary': 'rgb(var(--text-primary) / <alpha-value>)',
        'text-secondary': 'rgb(var(--text-secondary) / <alpha-value>)',
        'text-muted': 'rgb(var(--text-muted) / <alpha-value>)',
        /* ── Semantic roles ───────────────────────────────────────────────
           good        favorable scientific outcomes (strong hits, passing QC)
           warn        data-unfavorable but NOT errors (weak hits, low confidence)
           info        neutral scientific information (accessions, chain features)
           error       real errors only (red is reserved for genuine failures)
           molecule / interaction  domain-specific data channel colours     */
        good: 'rgb(var(--good) / <alpha-value>)',
        warn: 'rgb(var(--warn) / <alpha-value>)',
        info: 'rgb(var(--info) / <alpha-value>)',
        error: {
          DEFAULT: 'rgb(var(--error) / <alpha-value>)',
          dim:     'rgba(239,68,68,0.15)',
        },
        molecule: {
          protein: 'rgb(var(--molecule-protein) / <alpha-value>)',
          dna:     'rgb(var(--molecule-dna) / <alpha-value>)',
          rna:     'rgb(var(--molecule-rna) / <alpha-value>)',
        },
        interaction: {
          hbond:       'rgb(var(--interaction-hbond) / <alpha-value>)',
          hydrophobic: 'rgb(var(--interaction-hydrophobic) / <alpha-value>)',
          pi:          'rgb(var(--interaction-pi) / <alpha-value>)',
          salt:        'rgb(var(--interaction-salt) / <alpha-value>)',
        },
        // Static cool hairlines — legible on both dark and light canvases.
        glass: 'rgba(100,110,180,0.07)',
        'glass-hover': 'rgba(100,110,180,0.13)',
        'glass-border': 'rgb(var(--glass-border) / var(--glass-border-a))',
        'glass-border-soft': 'rgba(100,110,180,0.07)',
        'glass-border-bright': 'rgba(45,212,191,0.2)',
        // 3D-viewer / canvas scene background + floating HUD chrome.
        viewer: 'rgb(var(--viewer-bg) / <alpha-value>)',
        hud: 'rgb(var(--hud-chip-bg) / <alpha-value>)',
        'hud-text': 'rgb(var(--hud-chip-text) / <alpha-value>)',
        'hud-line': 'rgb(var(--hud-chip-line) / <alpha-value>)',
        confidence: {
          'very-high': 'rgb(var(--confidence-very-high) / <alpha-value>)',
          high:        'rgb(var(--confidence-high) / <alpha-value>)',
          moderate:    'rgb(var(--confidence-moderate) / <alpha-value>)',
          low:         'rgb(var(--confidence-low) / <alpha-value>)',
        },
      },
      fontFamily: {
        display: ['var(--font-geist-sans)', 'system-ui', 'sans-serif'],
        body:    ['var(--font-geist-sans)', 'system-ui', 'sans-serif'],
        mono:    ['var(--font-geist-mono)', 'ui-monospace', 'monospace'],
        sans:    ['var(--font-geist-sans)', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-cyan':   'var(--shadow-glow-cyan)',
        'glow-purple': 'var(--shadow-glow-purple)',
        'glow-amber':  'var(--shadow-glow-amber)',
        'glass-sm':  'var(--shadow-glass-sm)',
        'glass-md':  'var(--shadow-glass-md)',
        'glass-lg':  'var(--shadow-glass-lg)',
        'nav-active': 'var(--shadow-nav-active)',
        'clay':      'var(--shadow-clay)',
        'clay-press':'var(--shadow-clay-press)',
        'critical':  'var(--shadow-critical)',
        'data-card': 'var(--shadow-data-card)',
        'float':     'var(--shadow-float)',
        'float-sm':  'var(--shadow-float-sm)',
      },
      backgroundImage: {
        'grid-subtle':
          'linear-gradient(rgba(100,110,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(100,110,255,0.05) 1px, transparent 1px)',
        'radial-vignette':
          'radial-gradient(ellipse 80% 80% at 50% 50%, transparent 25%, var(--vignette-mid) 70%, var(--vignette-edge) 100%)',
        'gradient-cyan-purple':
          'linear-gradient(135deg, #2DD4BF 0%, #8B93D6 100%)',
        'gradient-surface':
          'linear-gradient(180deg, rgb(var(--bg-surface-0)) 0%, rgb(var(--bg-void)) 100%)',
      },
      backgroundSize: {
        grid: '50px 50px',
      },
      animation: {
        'float':       'float 6s ease-in-out infinite',
        'float-slow':  'float 9s ease-in-out infinite',
        'glow-pulse':  'glow-pulse 3s ease-in-out infinite',
        'spin-slow':   'spin 20s linear infinite',
        'scan':        'scan 2.5s ease-in-out infinite',
        'slide-up':    'slideUp 0.5s ease-out forwards',
        'fade-in':     'fadeIn 0.5s ease-out forwards',
        fadeUp:        'fadeUp 0.6s ease-out forwards',
        typewriter:    'typewriter 3s steps(40) forwards',
        blink:         'blink 0.75s step-end infinite',
        pulse:         'pulse 2s cubic-bezier(0.4,0,0.6,1) infinite',
      },
      keyframes: {
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':      { transform: 'translateY(-12px)' },
        },
        'glow-pulse': {
          '0%, 100%': { opacity: '0.5' },
          '50%':      { opacity: '1' },
        },
        scan: {
          '0%':   { transform: 'translateY(-100%)' },
          '100%': { transform: 'translateY(200%)' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(16px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        fadeIn: {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        fadeUp: {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
        typewriter: {
          from: { width: '0' },
          to:   { width: '100%' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%':      { opacity: '0' },
        },
      },
      maxWidth: {
        content: '1280px',
      },
      borderRadius: {
        '2xl': '1rem',
        '3xl': '1.25rem',
        '4xl': '1.5rem',
      },
      transitionTimingFunction: {
        'spring':    'cubic-bezier(0.25, 0.1, 0.25, 1)',
        'out-quart': 'cubic-bezier(0.25, 1, 0.5, 1)',
      },
    },
  },
  plugins: [],
};

export default config;
