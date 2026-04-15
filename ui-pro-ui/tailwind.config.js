/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
    './lib/**/*.{js,ts,jsx,tsx}',
    './styles/**/*.{js,ts,jsx,tsx}',
    './features/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        /* 🎨 Colors from design tokens */
        bg: {
          primary: '#020617',      // deep dark
          secondary: '#0f172a',    // panels
          tertiary: '#020617cc',   // overlays
        },

        surface: {
          primary: '#0f172a',
          secondary: '#1e293b',
          hover: '#334155',
        },

        border: {
          subtle: '#1e293b',
          default: '#334155',
          strong: '#475569',
        },

        text: {
          primary: '#f8fafc',
          secondary: '#cbd5f5',
          muted: '#64748b',
          disabled: '#475569',
        },

        accent: {
          primary: '#7c3aed',   // violet
          hover: '#6d28d9',
          soft: '#a78bfa33',
        },

        success: '#22c55e',
        warning: '#eab308',
        error: '#ef4444',
      },

      /* 🧊 Radius */
      borderRadius: {
        sm: '6px',
        md: '10px',
        lg: '14px',
        xl: '18px',
        full: '999px',
      },

      /* 📏 Spacing */
      spacing: {
        xs: '4px',
        sm: '8px',
        md: '12px',
        lg: '16px',
        xl: '24px',
        xxl: '32px',
      },

      /* 🔤 Typography */
      fontSize: {
        xs: '12px',
        sm: '13px',
        md: '14px',
        lg: '16px',
        xl: '18px',
        xxl: '20px',
      },

      fontFamily: {
        inter: ['Inter, sans-serif'],
      },

      /* ✨ Shadows */
      boxShadow: {
        sm: '0 1px 2px rgba(0,0,0,0.2)',
        md: '0 4px 12px rgba(0,0,0,0.4)',
        lg: '0 10px 30px rgba(0,0,0,0.6)',
      },
      /* Keep slate for backwards compatibility */
      slate: {
        950: '#0a0a0f',
      },
    },
  },
  plugins: [],
}
