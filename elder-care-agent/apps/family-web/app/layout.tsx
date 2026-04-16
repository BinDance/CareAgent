import './globals.css';
import type { Metadata } from 'next';

export const metadata: Metadata = {
  title: '家属端总览',
  description: '老年陪护 Agent 家属端'
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
