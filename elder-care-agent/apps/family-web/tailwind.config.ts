import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './app/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './lib/**/*.{ts,tsx}',
    '../../packages/ui/src/**/*.{ts,tsx}'
  ],
  theme: {
    extend: {
      fontFamily: {
        display: ['Trebuchet MS', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'sans-serif']
      },
      colors: {
        family: {
          ink: '#14213d',
          warm: '#f4efe6',
          gold: '#e6a84b',
          teal: '#1f6f78',
          coral: '#b14a3b'
        }
      }
    }
  },
  plugins: []
};

export default config;
