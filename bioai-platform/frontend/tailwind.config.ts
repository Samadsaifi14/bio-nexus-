import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
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
        void: '#04040A',
        surface: {
          0: '#080812',
          1: '#0D0D1A',
          2: '#111122',
          3: '#151528',
        },
        'accent-cyan': '#00F5D4',
        'accent-purple': '#8B5CF6',
        'accent-amber': '#F59E0B',
        'text-primary': '#F0F0FF',
        'text-secondary': '#8890AA',
        'text-muted': '#4A4F6A',
        glass: 'rgba(100,110,180,0.07)',
        'glass-hover': 'rgba(100,110,180,0.13)',
        'glass-border': 'rgba(100,110,180,0.12)',
        'glass-border-bright': 'rgba(0,245,212,0.2)',
        base: {
          50:  '#f8fafc',
          100: '#f1f5f9',
          200: '#e2e8f0',
          300: '#cbd5e1',
          400: '#94a3b8',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        },
        border: {
          DEFAULT: 'rgba(100,110,180,0.12)',
          subtle: 'rgba(100,110,180,0.07)',
          bright: 'rgba(0,245,212,0.2)',
        },
        accent: {
          DEFAULT: '#00F5D4',
          dim:     'rgba(0,245,212,0.15)',
          hover:   '#00dbbe',
        },
        confidence: {
          high:   '#00F5D4',
          medium: '#F59E0B',
          low:    '#EF4444',
        },
        error: {
          DEFAULT: '#EF4444',
          dim:     'rgba(239,68,68,0.15)',
        },
      },
      fontFamily: {
        display: ['Space Grotesk', 'sans-serif'],
        body:    ['Inter', 'sans-serif'],
        mono:    ['JetBrains Mono', 'monospace'],
        sans:    ['Inter', 'sans-serif'],
      },
      boxShadow: {
        'glow-cyan':   '0 0 20px rgba(0,245,212,0.2), 0 0 60px rgba(0,245,212,0.08)',
        'glow-purple': '0 0 20px rgba(139,92,246,0.2), 0 0 60px rgba(139,92,246,0.08)',
        'glow-amber':  '0 0 20px rgba(245,158,11,0.2)',
        'glass-sm':  '0 2px 16px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04)',
        'glass-md':  '0 4px 32px rgba(0,0,0,0.45), inset 0 1px 0 rgba(255,255,255,0.04)',
        'glass-lg':  '0 8px 48px rgba(0,0,0,0.55), inset 0 1px 0 rgba(255,255,255,0.05)',
        'nav-active': 'inset 2px 0 0 #00F5D4',
      },
      backgroundImage: {
        'grid-subtle':
          'linear-gradient(rgba(100,110,255,0.05) 1px, transparent 1px), linear-gradient(90deg, rgba(100,110,255,0.05) 1px, transparent 1px)',
        'radial-vignette':
          'radial-gradient(ellipse 80% 80% at 50% 50%, transparent 25%, rgba(4,4,10,0.65) 70%, rgba(4,4,10,0.97) 100%)',
        'gradient-cyan-purple':
          'linear-gradient(135deg, #00F5D4 0%, #8B5CF6 100%)',
        'gradient-surface':
          'linear-gradient(180deg, #080812 0%, #04040A 100%)',
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
