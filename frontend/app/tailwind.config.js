/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,jsx}',
  ],
  theme: {
    extend: {
      colors: {
        navy: {
          DEFAULT: '#0A2540',
          50: '#F1F5F9',
          100: '#E2E8F0',
          800: '#13325A',
          900: '#0A2540',
          950: '#06182B',
        },
        gold: {
          DEFAULT: '#D4AF37',
          soft: '#E6C757',
          deep: '#A8851F',
        },
        risk: {
          healthy: '#10B981',
          watch: '#F59E0B',
          warning: '#F97316',
          critical: '#EF4444',
        },
        severity: {
          info: '#3B82F6',
          warning: '#F97316',
          critical: '#EF4444',
        },
        canvas: '#F8FAFC',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        card: '0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)',
      },
      borderRadius: {
        xl: '0.875rem',
      },
    },
  },
  plugins: [],
};
