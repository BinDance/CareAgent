import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    '../../packages/ui/src/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['Georgia', 'STKaiti', 'KaiTi', 'serif']
      },
      colors: {
        elder: {
          ink: '#1f1a17',
          shell: '#fbf3df',
          sun: '#f39b2f',
          moss: '#55705e',
          berry: '#b94a48'
        }
      },
      boxShadow: {
        halo: '0 0 0 18px rgba(243, 155, 47, 0.12)'
      }
    }
  },
  plugins: []
};

export default config;
