/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{vue,js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['Acme', 'sans-serif'],
        narrative: ['Newsreader', 'serif'],
        ui: ['Acme', 'sans-serif'],
        sans: ['Acme', 'sans-serif'], // Default to UI font
      },
      colors: {
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
        'spin-slow': 'spin 3s linear infinite',
      }
    },
  },
  plugins: [],
}
