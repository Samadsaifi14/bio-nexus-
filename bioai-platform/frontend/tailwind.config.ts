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
        void: '#06060B',
        surface: {
          0: '#080812',
          1: '#0D0D1A',
          2: '#111122',
          3: '#151528',
        },
        'accent-cyan': '#2DD4BF',
        'accent-hover': '#3BDCC7',
        'accent-purple': '#8B93D6',
        'accent-amber': '#E0A94E',
        'text-primary': '#DDE0EE',
        'text-secondary': '#A5AEC6',
        'text-muted': '#848CA4',
        /* ── Semantic roles ───────────────────────────────────────────────
           good        favorable scientific outcomes (strong hits, passing QC)
           warn        data-unfavorable but NOT errors (weak hits, low confidence)
           info        neutral scientific information (accessions, chain features)
           error       real errors only (red is reserved for genuine failures)
           molecule / interaction  domain-specific data channel colours     */
        good: '#34D399',
        warn: '#FBBF24',
        info: '#60A5FA',
        error: {
          DEFAULT: '#EF4444',
          dim:     'rgba(239,68,68,0.15)',
        },
        molecule: {
          protein: '#60A5FA',
          dna:     '#8B93D6',
          rna:     '#FB923C',
        },
        interaction: {
          hbond:       '#60A5FA',
          hydrophobic: '#FBBF24',
          pi:          '#A78BFA',
          salt:        '#22D3EE',
        },
        glass: 'rgba(100,110,180,0.07)',
        'glass-hover': 'rgba(100,110,180,0.13)',
        'glass-border': 'rgba(100,110,180,0.12)',
        'glass-border-bright': 'rgba(45,212,191,0.2)',
        confidence: {
          'very-high': '#2DD4BF',
          high:        '#60A5FA',
          moderate:    '#FBBF24',
          low:         '#94A3B8',
        },
      },
      fontFamily: {
        display: ['var(--font-geist-sans)', 'system-ui', 'sans-serif'],
        body:    ['var(--font-geist-sans)', 'system-ui', 'sans-serif'],
        mono:    ['var(--font-geist-mono)', 'ui-monospace', 'monospace'],
        sans:    ['var(--font-geist-sans)', 'system-ui', 'sans-serif'],
      },
      boxShadow: {
        'glow-cyan':   '0 1px 2px rgba(0,0,0,0.35), 0 10px 28px rgba(45,212,191,0.07)',
        'glow-purple': '0 1px 2px rgba(0,0,0,0.35), 0 10px 28px rgba(139,147,214,0.07)',
        'glow-amber':  '0 1px 2px rgba(0,0,0,0.35), 0 10px 24px rgba(224,169,78,0.07)',
        'glass-sm':  '0 2px 16px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)',
        'glass-md':  '0 4px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.04)',
        'glass-lg':  '0 8px 48px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.05)',
        'nav-active': 'inset 2px 0 0 #2DD4BF',
        'clay':      '5px 5px 12px rgba(0,0,0,0.5), -3px -3px 8px rgba(255,255,255,0.03), inset 0 1px 0 rgba(255,255,255,0.05)',
        'clay-press':'3px 3px 8px rgba(0,0,0,0.5), -2px -2px 6px rgba(255,255,255,0.02), inset 0 2px 6px rgba(0,0,0,0.35)',
        'critical':  '0 2px 0 rgba(0,0,0,0.3), 0 6px 16px rgba(0,0,0,0.4)',
        'data-card': '0 1px 2px rgba(0,0,0,0.35)',
      },
      backgroundImage: {
        'grid-subtle':
          'linear-gradient(rgba(100,110,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(100,110,255,0.05) 1px, transparent 1px)',
        'radial-vignette':
          'radial-gradient(ellipse 80% 80% at 50% 50%, transparent 25%, rgba(6,6,11,0.65) 70%, rgba(6,6,11,0.97) 100%)',
        'gradient-cyan-purple':
          'linear-gradient(135deg, #2DD4BF 0%, #8B93D6 100%)',
        'gradient-surface':
          'linear-gradient(180deg, #080812 0%, #06060B 100%)',
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
