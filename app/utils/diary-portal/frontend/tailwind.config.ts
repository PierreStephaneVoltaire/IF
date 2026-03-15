import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // Mental health score colors
        score: {
          high: '#22c55e', // green-500 (7+)
          mid: '#eab308', // yellow-500 (5-7)
          low: '#ef4444', // red-500 (<5)
        },
      },
    },
  },
  plugins: [],
} satisfies Config
