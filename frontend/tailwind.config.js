/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        offense: {
          light: '#fef3c7',
          DEFAULT: '#f59e0b',
          dark: '#b45309',
        },
        defense: {
          light: '#dbeafe',
          DEFAULT: '#3b82f6',
          dark: '#1d4ed8',
        },
        // Semantic surface tokens — driven by CSS variables in styles/index.css
        // so the palette swaps automatically with the `.dark` class strategy.
        // Using the `<alpha-value>` placeholder lets utilities like
        // `bg-surface-2/80` work as expected.
        surface: 'rgb(var(--color-surface) / <alpha-value>)',
        'surface-2': 'rgb(var(--color-surface-2) / <alpha-value>)',
        'surface-3': 'rgb(var(--color-surface-3) / <alpha-value>)',
        'border-subtle': 'rgb(var(--color-border-subtle) / <alpha-value>)',
        'border-default': 'rgb(var(--color-border-default) / <alpha-value>)',
        'text-primary': 'rgb(var(--color-text-primary) / <alpha-value>)',
        'text-secondary': 'rgb(var(--color-text-secondary) / <alpha-value>)',
        'text-muted': 'rgb(var(--color-text-muted) / <alpha-value>)',
        // Stat polarity scale — pairs with `getPolarityClass` / `getPolarityIcon`
        // in `lib/utils.ts`. Three stops per polarity so call sites can pick
        // soft (background tint), default (foreground), strong (emphasis).
        pos: {
          soft: 'rgb(var(--color-pos-soft) / <alpha-value>)',
          DEFAULT: 'rgb(var(--color-pos) / <alpha-value>)',
          strong: 'rgb(var(--color-pos-strong) / <alpha-value>)',
        },
        neg: {
          soft: 'rgb(var(--color-neg-soft) / <alpha-value>)',
          DEFAULT: 'rgb(var(--color-neg) / <alpha-value>)',
          strong: 'rgb(var(--color-neg-strong) / <alpha-value>)',
        },
        warn: {
          soft: 'rgb(var(--color-warn-soft) / <alpha-value>)',
          DEFAULT: 'rgb(var(--color-warn) / <alpha-value>)',
          strong: 'rgb(var(--color-warn-strong) / <alpha-value>)',
        },
        neutral: {
          soft: 'rgb(var(--color-neutral-soft) / <alpha-value>)',
          DEFAULT: 'rgb(var(--color-neutral) / <alpha-value>)',
          strong: 'rgb(var(--color-neutral-strong) / <alpha-value>)',
        },
      },
      // Type ramp — six steps + display. Tuple = [size, lineHeight]. Mirrors
      // the cadence used across cortex tabs (10px micro labels, 12px caption,
      // 14px body, 18/24/32px headings, 40px hero).
      fontSize: {
        micro: ['0.625rem', { lineHeight: '0.875rem' }],   // 10px / 14px
        caption: ['0.75rem', { lineHeight: '1rem' }],       // 12px / 16px
        body: ['0.875rem', { lineHeight: '1.25rem' }],      // 14px / 20px
        h3: ['1.125rem', { lineHeight: '1.5rem' }],         // 18px / 24px
        h2: ['1.5rem', { lineHeight: '2rem' }],             // 24px / 32px
        h1: ['2rem', { lineHeight: '2.5rem' }],             // 32px / 40px
        display: ['2.5rem', { lineHeight: '3rem' }],        // 40px / 48px
      },
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', 'Liberation Mono', 'Courier New', 'monospace'],
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'Noto Sans', 'sans-serif'],
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
      },
      animation: {
        fadeUp: 'fadeUp 0.4s ease-out',
      },
    },
  },
  plugins: [
    // Numeric utilities — `tabular-nums` for stat columns, `oldstyle-nums` etc.
    // Tailwind 3.4 ships these as built-in `font-variant-numeric` utilities,
    // but we expose a tiny custom plugin to ensure they're available even when
    // the default plugin set is restricted by future config changes.
    function ({ addUtilities }) {
      addUtilities({
        '.tabular-nums': { 'font-variant-numeric': 'tabular-nums' },
        '.proportional-nums': { 'font-variant-numeric': 'proportional-nums' },
        '.lining-nums': { 'font-variant-numeric': 'lining-nums' },
      })
    },
  ],
}
