/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        dark: {
          950: '#020617', // OLED Deep Black / base slate-950
          900: '#0b1120', // Surface Panel
          850: '#0f172a', // Card / Surface
          800: '#1e293b', // Surface Elevated / Modal / Dropdown
          700: '#334155', // Border Primary
          600: '#475569', // Border Subtle / DAG Edge
          500: '#64748b', // Text Muted / Placeholder
          400: '#94a3b8', // Text Secondary
          300: '#cbd5e1',
          100: '#f1f5f9',
          50:  '#f8fafc',
        },
        brand: {
          DEFAULT: '#3b82f6',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          glow: 'rgba(59, 130, 246, 0.25)',
        },
        emerald: {
          DEFAULT: '#10b981',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          glow: 'rgba(16, 185, 129, 0.25)',
        },
        fraud: {
          DEFAULT: '#ef4444',
          400: '#f87171',
          500: '#ef4444',
          600: '#dc2626',
          900: '#7f1d1d',
          glow: 'rgba(239, 68, 68, 0.25)',
        },
        legit: {
          DEFAULT: '#10b981',
          400: '#34d399',
          500: '#10b981',
          600: '#059669',
          glow: 'rgba(16, 185, 129, 0.25)',
        },
        alarm: {
          DEFAULT: '#f59e0b',
          400: '#fbbf24',
          500: '#f59e0b',
          600: '#d97706',
          glow: 'rgba(245, 158, 11, 0.25)',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Fira Code"', 'Menlo', 'Monaco', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'glow-blue': '0 0 15px rgba(59, 130, 246, 0.25)',
        'glow-green': '0 0 15px rgba(16, 185, 129, 0.25)',
        'glow-red': '0 0 15px rgba(239, 68, 68, 0.25)',
        'glow-amber': '0 0 15px rgba(245, 158, 11, 0.25)',
      },
      spacing: {
        'topbar': '56px',
        'bottombar': '28px',
        'sidebar': '240px',
        'sidebar-collapsed': '64px',
      }
    },
  },
  plugins: [],
}
