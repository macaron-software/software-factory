/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './app/**/*.{js,ts,jsx,tsx}',
    './components/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg: { 0: 'var(--bg-0)', 1: 'var(--bg-1)', 2: 'var(--bg-2)', 3: 'var(--bg-3)', hover: 'var(--bg-hover)', active: 'var(--bg-active)' },
        bd: { 1: 'var(--border-1)', 2: 'var(--border-2)' },
        t: { 1: 'var(--text-1)', 2: 'var(--text-2)', 3: 'var(--text-3)', 4: 'var(--text-4)', 5: 'var(--text-5)', 6: 'var(--text-6)' },
        accent: { DEFAULT: 'var(--accent)', 2: 'var(--accent-2)', 3: 'var(--accent-3)', dim: 'var(--accent-dim)', bg: 'var(--accent-bg)' },
        gain: { DEFAULT: 'var(--green)', light: 'var(--green-light)', bg: 'var(--green-bg)', mid: 'var(--green-mid)' },
        loss: { DEFAULT: 'var(--red)', light: 'var(--red-light)', bg: 'var(--red-bg)', mid: 'var(--red-mid)' },
        warn: { DEFAULT: 'var(--orange)', bg: 'var(--orange-bg)' },
        info: { DEFAULT: 'var(--blue)', light: 'var(--blue-light)' },
      },
      fontSize: {
        'caption': ['10px', { lineHeight: '1.4', letterSpacing: '0.06em' }],
        'label': ['11px', { lineHeight: '1.4', letterSpacing: '0.04em' }],
        'body': ['13px', { lineHeight: '1.5' }],
        'body-lg': ['14px', { lineHeight: '1.5' }],
        'title': ['15px', { lineHeight: '1.3' }],
        'heading': ['18px', { lineHeight: '1.3' }],
        'hero': ['32px', { lineHeight: '1', letterSpacing: '-0.02em' }],
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        xl: 'var(--radius-xl)',
        pill: 'var(--radius-pill)',
      },
    },
  },
  plugins: [],
}
