import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '老人陪护语音端',
  description: '老人陪护 Agent 语音页面'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
