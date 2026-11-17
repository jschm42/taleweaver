/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Acme', 'sans-serif'],
        narrative: ['Newsreader', 'serif'],
        fantasy: ['Cinzel', 'Newsreader', 'serif'],
        ui: ['Acme', 'sans-serif'],
        sans: ['Acme', 'sans-serif'], // Default to UI font
        wb: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'], // Workbench body font
      },
      fontSize: {
        'xxs': ['0.75rem', { lineHeight: '1rem' }],    // 12px
        'xs': ['0.8125rem', { lineHeight: '1.125rem' }], // 13px
        'sm': ['0.9375rem', { lineHeight: '1.25rem' }],  // 15px
        'base': ['1.0625rem', { lineHeight: '1.5rem' }], // 17px
      },
      colors: {
        // Workbench tokens (docs/specs/workbench_ui.md); values live in src/assets/workbench.css.
        wb: {
          canvas: 'rgb(var(--wb-canvas) / <alpha-value>)',
          surface: 'rgb(var(--wb-surface) / <alpha-value>)',
          raised: 'rgb(var(--wb-raised) / <alpha-value>)',
          overlay: 'rgb(var(--wb-overlay) / <alpha-value>)',
          line: 'var(--wb-line)',
          'line-strong': 'var(--wb-line-strong)',
          strong: 'rgb(var(--wb-strong) / <alpha-value>)',
          body: 'rgb(var(--wb-body) / <alpha-value>)',
          muted: 'rgb(var(--wb-muted) / <alpha-value>)',
          faint: 'rgb(var(--wb-faint) / <alpha-value>)',
          accent: {
            DEFAULT: 'rgb(var(--wb-accent) / <alpha-value>)',
            text: 'rgb(var(--wb-accent-text) / <alpha-value>)',
            soft: 'rgb(var(--wb-accent) / 0.12)',
          },
          ai: {
            DEFAULT: 'rgb(var(--wb-ai) / <alpha-value>)',
            text: 'rgb(var(--wb-ai-text) / <alpha-value>)',
            soft: 'rgb(var(--wb-ai) / 0.12)',
          },
          info: {
            DEFAULT: 'rgb(var(--wb-info) / <alpha-value>)',
            text: 'rgb(var(--wb-info-text) / <alpha-value>)',
            soft: 'rgb(var(--wb-info) / 0.12)',
          },
          warn: {
            DEFAULT: 'rgb(var(--wb-warn) / <alpha-value>)',
            text: 'rgb(var(--wb-warn-text) / <alpha-value>)',
            soft: 'rgb(var(--wb-warn) / 0.12)',
          },
          danger: {
            DEFAULT: 'rgb(var(--wb-danger) / <alpha-value>)',
            text: 'rgb(var(--wb-danger-text) / <alpha-value>)',
            soft: 'rgb(var(--wb-danger) / 0.12)',
          },
        },
        aether: {
          background: '#081425',
          surface: '#152031',
          'surface-bright': '#2f3a4c',
          'surface-low': '#111c2d',
          primary: '#4edea3',
          'primary-container': '#10b981',
          secondary: '#d0bcff',
          'secondary-container': '#571bc1',
          tertiary: '#bec6e0',
          outline: '#86948a',
          charcoal: '#121212',
        }
      },
      boxShadow: {
        'wb-float': '0 16px 40px rgb(0 0 0 / 0.45), 0 0 0 1px rgb(255 255 255 / 0.06)',
        'ambient-emerald': '0 0 20px rgba(78, 222, 163, 0.15)',
        'ambient-purple': '0 0 20px rgba(208, 188, 255, 0.15)',
        'glass': 'inset 0 0 0 1px rgba(255, 255, 255, 0.05)',
        'glassedge': 'inset 0 1px 1px 0 rgba(255, 255, 255, 0.1)',
      },
      backgroundImage: {
        'glass-gradient': 'linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0) 100%)',
        'card-gradient': 'linear-gradient(to bottom right, #121212, #081425)',
        'card-emerald': 'linear-gradient(135deg, #121212 0%, #06201a 100%)',
        'card-purple': 'linear-gradient(135deg, #121212 0%, #150a25 100%)',
      },
      animation: {
        'pulse-slow': 'pulse 4s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-subtle': 'pulse-subtle 3s ease-in-out infinite',
        'spin-slow': 'spin 3s linear infinite',
      },
      keyframes: {
        'pulse-subtle': {
          '0%, 100%': { opacity: 1 },
          '50%': { opacity: 0.7 },
        }
      }
    },
  },
  plugins: [],
}
