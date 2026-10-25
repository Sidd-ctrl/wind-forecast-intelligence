export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        void: 'var(--void)',
        obsidian: 'var(--obsidian)',
        graphite: {
          900: 'var(--graphite-900)',
          800: 'var(--graphite-800)',
          700: 'var(--graphite-700)',
          600: 'var(--graphite-600)'
        },
        paper: 'var(--paper)',
        'paper-dim': 'var(--paper-dim)',
        muted: 'var(--muted)',
        'muted-dim': 'var(--muted-dim)',
        lime: 'var(--lime)',
        amber: 'var(--amber)',
        teal: 'var(--teal)'
      },
      fontFamily: {
        sans: 'var(--font-sans)',
        mono: 'var(--font-mono)'
      },
      borderColor: {
        hairline: 'var(--hairline)',
        'hairline-strong': 'var(--hairline-strong)'
      }
    }
  },
  plugins: []
}
