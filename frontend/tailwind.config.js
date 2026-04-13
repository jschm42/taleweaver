/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        // Pixel-art / retro monospace font loaded via Google Fonts
        pixel: ['"Press Start 2P"', 'monospace'],
        // Modern UI font
        sans: ['Inter', 'sans-serif'],
      },
      colors: {
        // Dark fantasy palette
        parchment: '#f5e6c8',
        'parchment-dark': '#d4b896',
        ink: '#1a0a00',
        'ink-light': '#3d1f00',
        gold: '#c9a84c',
        'gold-light': '#f0d080',
        crimson: '#8b0000',
        'crimson-light': '#c0392b',
        emerald: '#1a5c2a',
        'emerald-light': '#27ae60',
        sapphire: '#1a2a5c',
        'sapphire-light': '#2980b9',
        // UI chrome
        'panel-bg': '#0d0d0d',
        'panel-border': '#3a2a1a',
        'panel-border-gold': '#8b6914',
      },
      boxShadow: {
        rpg: '0 0 0 3px #3a2a1a, 0 0 0 6px #8b6914, inset 0 0 20px rgba(0,0,0,0.5)',
        'rpg-gold': '0 0 0 3px #8b6914, 0 0 0 6px #c9a84c, inset 0 0 20px rgba(0,0,0,0.5)',
        glow: '0 0 8px rgba(201,168,76,0.6)',
      },
      animation: {
        'blink-cursor': 'blink 1s step-end infinite',
        'fade-in': 'fadeIn 0.3s ease-in',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        blink: { '0%, 100%': { opacity: '1' }, '50%': { opacity: '0' } },
        fadeIn: { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp: { from: { transform: 'translateY(20px)', opacity: '0' }, to: { transform: 'translateY(0)', opacity: '1' } },
      },
    },
  },
  plugins: [],
}
