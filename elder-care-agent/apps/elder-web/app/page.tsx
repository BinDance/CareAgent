import { Suspense } from 'react';

import { ElderVoicePanel } from '../components/elder-voice-panel';

export default function HomePage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-[#f7efe0]" />}>
      <ElderVoicePanel />
    </Suspense>
  );
}
