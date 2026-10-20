/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}', '../tests/frontend/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        navy: {
          50: '#eef2f9',
          100: '#d4dceb',
          200: '#a9b9d7',
          300: '#7e96c3',
          400: '#5373af',
          500: '#3a5a96',
          600: '#2c4676',
          700: '#1f3356',
          800: '#152340',
          900: '#0b1529',
          950: '#060c18',
        },
      },
    },
  },
  plugins: [],
};
