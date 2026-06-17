import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        base: {
          DEFAULT: '#0A0E14',
          surface: '#11161F',
          elevated: '#1A212E',
        },
        border: {
          subtle: '#232B3A',
        },
        accent: {
          DEFAULT: '#2DD4BF',
          bright: '#5EEAD4',
          glow: 'rgba(45, 212, 191, 0.15)',
        },
        text: {
          primary: '#E6EDF3',
          secondary: '#8B97A8',
          tertiary: '#5C6878',
        },
        confidence: {
          veryHigh: '#2DD4BF',
          high: '#60A5FA',
          moderate: '#FBBF24',
          low: '#94A3B8',
        },
        error: {
          DEFAULT: '#F87171',
        },
      },
      fontFamily: {
        display: ['"Space Grotesk"', 'sans-serif'],
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      maxWidth: {
        content: '1280px',
      },
      spacing: {
        18: '4.5rem',
      },
      keyframes: {
        typewriter: {
          '0%': { width: '0%' },
          '100%': { width: '100%' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0' },
        },
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulse: {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.5' },
        },
      },
      animation: {
        typewriter: 'typewriter 3s steps(60) forwards',
        blink: 'blink 0.8s step-end infinite',
        fadeUp: 'fadeUp 0.2s ease-out forwards',
        pulse: 'pulse 2s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};

export default config;
