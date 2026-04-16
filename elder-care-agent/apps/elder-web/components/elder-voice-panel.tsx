'use client';

import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';

import { getTodayReminders, sendVoiceInput, type TodayRemindersResult } from '../lib/api';
import { createSpeechRecognition, getSpeechCapability, speakText } from '../lib/speech';

type ViewState = 'idle' | 'listening' | 'thinking' | 'speaking' | 'error' | 'unsupported';
type ReminderFeedItem = {
  id: string;
  kind: 'notice' | 'medication' | 'message' | 'cognition';
  title: string;
  detail: string;
  simulated_at: string;
};

const MINUTES_PER_DAY = 24 * 60;
const CLOCK_SPEED_OPTIONS = [1, 10, 30];

const statusText: Record<ViewState, string> = {
  idle: '点一下中间按钮说话，也可以直接打字',
  listening: '正在听',
  thinking: '正在思考',
  speaking: '正在回复',
  error: '这次没听清，也可以直接打字',
  unsupported: '当前浏览器不支持语音功能，可以直接打字'
};

function startOfToday() {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate());
}

function getMinutesFromDate(date: Date) {
  return date.getHours() * 60 + date.getMinutes();
}

function buildSimulatedDate(dayStart: Date, minutes: number) {
  return new Date(dayStart.getTime() + minutes * 60 * 1000);
}

function formatClock(date: Date) {
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  });
}

function formatMinuteLabel(minutes: number) {
  const normalized = Math.max(0, Math.min(MINUTES_PER_DAY - 1, minutes));
  const hour = Math.floor(normalized / 60);
  const minute = normalized % 60;
  return `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
}

function buildReminderFeedItems(reminders: TodayRemindersResult, simulatedAt: string) {
  const items: ReminderFeedItem[] = [];

  for (const notice of reminders.notices || []) {
    items.push({
      id: `notice:${notice.id}:${simulatedAt}`,
      kind: 'notice',
      title: '通知提醒',
      detail: notice.summarized_notice || '家属有新的提醒。',
      simulated_at: simulatedAt
    });
  }

  for (const medication of reminders.medications || []) {
    const detailParts = [
      medication.medication_name,
      medication.dose,
      medication.frequency,
      medication.meal_timing ? `建议${medication.meal_timing}服用` : ''
    ].filter(Boolean);
    items.push({
      id: `medication:${medication.id}:${simulatedAt}`,
      kind: 'medication',
      title: '服药提醒',
      detail: detailParts.join('，') || '到服药时间了。',
      simulated_at: simulatedAt
    });
  }

  for (const message of reminders.messages || []) {
    items.push({
      id: `message:${message.id}:${simulatedAt}`,
      kind: 'message',
      title: '家人留言',
      detail: message.summary_text || '家人有一条新留言。',
      simulated_at: simulatedAt
    });
  }

  for (const cognition of reminders.cognition || []) {
    items.push({
      id: `cognition:${cognition.id || simulatedAt}`,
      kind: 'cognition',
      title: cognition.theme || '轻度认知互动',
      detail: cognition.prompt || '我们来聊聊早饭后的感受吧。',
      simulated_at: simulatedAt
    });
  }

  return items;
}

export function ElderVoicePanel() {
  const [state, setState] = useState<ViewState>('idle');
  const [transcript, setTranscript] = useState('');
  const [subtitle, setSubtitle] = useState('您好，我在这儿，您按一下按钮就可以和我说话。');
  const [errorMessage, setErrorMessage] = useState('');
  const [typedInput, setTypedInput] = useState('');
  const [simulatedMinutes, setSimulatedMinutes] = useState(() => getMinutesFromDate(new Date()));
  const [clockRunning, setClockRunning] = useState(false);
  const [clockStepMinutes, setClockStepMinutes] = useState(10);
  const [reminderFeed, setReminderFeed] = useState<ReminderFeedItem[]>([]);

  const capability = useMemo(() => getSpeechCapability(), []);
  const dayStartRef = useRef(startOfToday());
  const previousSimulatedMinutesRef = useRef(getMinutesFromDate(new Date()));
  const initializedReminderLoopRef = useRef(false);

  useEffect(() => {
    if (!capability.recognition) {
      setState('unsupported');
    }
  }, [capability.recognition]);

  useEffect(() => {
    if (!clockRunning) {
      return;
    }
    const timer = window.setInterval(() => {
      setSimulatedMinutes((current) => {
        const next = Math.min(MINUTES_PER_DAY - 1, current + clockStepMinutes);
        if (next >= MINUTES_PER_DAY - 1) {
          setClockRunning(false);
        }
        return next;
      });
    }, 1000);
    return () => window.clearInterval(timer);
  }, [clockRunning, clockStepMinutes]);

  useEffect(() => {
    const previousMinutes = previousSimulatedMinutesRef.current;
    const currentSimulatedDate = buildSimulatedDate(dayStartRef.current, simulatedMinutes);
    const previousSimulatedDate = buildSimulatedDate(dayStartRef.current, previousMinutes);

    const presentReminders = async (reminders: TodayRemindersResult, simulatedAt: string) => {
      const nextItems = buildReminderFeedItems(reminders, simulatedAt);
      if (nextItems.length === 0) {
        return;
      }

      setReminderFeed((current) => [...nextItems, ...current].slice(0, 8));

      if (state === 'thinking' || state === 'listening') {
        return;
      }

      const spokenText = nextItems.map((item) => `${item.title}，${item.detail}`).join('。');
      setSubtitle(spokenText);
      setState('speaking');
      if (capability.synthesis) {
        speakText(spokenText);
      }
      window.setTimeout(() => {
        setState((current) => (current === 'speaking' ? 'idle' : current));
      }, Math.max(2500, spokenText.length * 160));
    };

    const loadCurrentMomentReminders = async () => {
      try {
        const reminders = await getTodayReminders(undefined, {
          nowTs: currentSimulatedDate.toISOString()
        });
        const simulatedAt = formatClock(currentSimulatedDate);
        await presentReminders(reminders, simulatedAt);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : '提醒查询失败');
      }
    };

    const loadRangeReminders = async () => {
      try {
        const reminders = await getTodayReminders(undefined, {
          nowTs: currentSimulatedDate.toISOString(),
          sinceTs: previousSimulatedDate.toISOString()
        });
        const simulatedAt = formatClock(currentSimulatedDate);
        await presentReminders(reminders, simulatedAt);
      } catch (error) {
        setErrorMessage(error instanceof Error ? error.message : '提醒查询失败');
      }
    };

    const isFirstTick = !initializedReminderLoopRef.current;
    initializedReminderLoopRef.current = true;
    previousSimulatedMinutesRef.current = simulatedMinutes;

    if (isFirstTick) {
      void loadCurrentMomentReminders();
      return;
    }

    if (simulatedMinutes < previousMinutes) {
      setReminderFeed([]);
      void loadCurrentMomentReminders();
      return;
    }

    if (simulatedMinutes === previousMinutes) {
      return;
    }

    void loadRangeReminders();
  }, [capability.synthesis, simulatedMinutes, state]);

  const runConversation = async (text: string) => {
    setTranscript(text);
    setState('thinking');
    try {
      const result = await sendVoiceInput(text, undefined, {
        nowTs: buildSimulatedDate(dayStartRef.current, simulatedMinutes).toISOString()
      });
      setSubtitle(result.subtitle || result.reply_text);
      setState('speaking');
      if (result.should_speak && capability.synthesis) {
        speakText(result.reply_text);
        window.setTimeout(() => setState('idle'), Math.max(2500, result.reply_text.length * 180));
      } else {
        setState('idle');
      }
    } catch (error) {
      setState('error');
      setErrorMessage(error instanceof Error ? error.message : '请求失败');
    }
  };

  const startListening = () => {
    if (!capability.recognition) {
      setState('unsupported');
      return;
    }
    const controller = createSpeechRecognition({
      onStart: () => {
        setState('listening');
        setErrorMessage('');
      },
      onResult: async (text) => {
        await runConversation(text);
      },
      onError: (message) => {
        setState('error');
        setErrorMessage(message);
      },
      onEnd: () => {
        setState((current) => (current === 'listening' ? 'idle' : current));
      }
    });
    controller?.start();
  };

  const submitTypedText = async () => {
    if (!typedInput.trim()) return;
    await runConversation(typedInput.trim());
    setTypedInput('');
  };

  const handleTypedInputKeyDown = async (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) {
      return;
    }
    event.preventDefault();
    await submitTypedText();
  };

  const simulatedDate = buildSimulatedDate(dayStartRef.current, simulatedMinutes);
  const hourRotation = (simulatedMinutes / 60) * 30;
  const minuteRotation = (simulatedMinutes % 60) * 6;
  const pingClass = state === 'listening' ? 'absolute inset-0 rounded-full animate-ping bg-orange-300/30' : 'absolute inset-0 rounded-full';

  return (
    <main className="min-h-screen px-5 py-8 text-elder-ink sm:px-8">
      <div className="mx-auto flex min-h-[calc(100vh-4rem)] max-w-5xl flex-col items-center justify-between rounded-[42px] border border-white/40 bg-white/20 px-6 py-8 shadow-halo backdrop-blur-md sm:px-10 sm:py-10">
        <div className="w-full text-center">
          <p className="text-base tracking-[0.2em] text-elder-moss/80">老人陪护交互端</p>
          <h1 className="mt-4 font-display text-4xl font-semibold sm:text-6xl">和我说说现在想做什么</h1>
          <p className="mt-5 text-2xl leading-relaxed text-elder-ink/80 sm:text-3xl">{statusText[state]}</p>
        </div>

        <button
          type="button"
          onClick={startListening}
          disabled={state === 'thinking'}
          className="group relative mt-8 flex h-56 w-56 items-center justify-center rounded-full border-[10px] border-white bg-[radial-gradient(circle_at_top,#ffd886,#f39b2f_60%,#ca6d1c)] text-white shadow-[0_22px_50px_rgba(161,98,34,0.28)] transition-transform duration-200 hover:scale-[1.02] disabled:cursor-not-allowed disabled:opacity-70 sm:h-72 sm:w-72"
        >
          <span className={pingClass} />
          <span className="relative text-8xl sm:text-9xl">麦</span>
        </button>

        <div className="mt-10 w-full rounded-[34px] border border-white/60 bg-[var(--card)] p-6 shadow-lg sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-xl font-semibold text-elder-moss sm:text-2xl">大字字幕</p>
            {!capability.recognition ? <span className="rounded-full bg-rose-100 px-4 py-2 text-lg text-rose-700">浏览器不支持语音识别</span> : null}
          </div>
          <p className="mt-5 text-3xl leading-relaxed sm:text-5xl">{subtitle}</p>
          {transcript ? <p className="mt-5 text-xl text-elder-ink/60 sm:text-2xl">您刚才说：{transcript}</p> : null}
          {errorMessage ? <p className="mt-4 text-xl text-elder-berry sm:text-2xl">{errorMessage}</p> : null}
        </div>

        <div className="mt-8 w-full rounded-[34px] border border-white/60 bg-[var(--card)] p-6 shadow-lg sm:p-8">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xl font-semibold text-elder-moss sm:text-2xl">模拟时钟</p>
              <p className="mt-2 text-base text-elder-ink/65 sm:text-lg">拖动时间或自动播放，页面会按这个时间检查用药、通知和留言提醒。</p>
              <p className="mt-5 font-display text-5xl text-elder-ink sm:text-6xl">{formatClock(simulatedDate)}</p>
              <p className="mt-2 text-lg text-elder-ink/60">当前模拟时间</p>
            </div>

            <div className="relative mx-auto flex h-40 w-40 items-center justify-center rounded-full border-[10px] border-white bg-[radial-gradient(circle_at_top,#fff6da,#f5e3ae_62%,#ebd18a)] shadow-[0_18px_40px_rgba(178,145,66,0.18)]">
              <div className="absolute h-3 w-3 rounded-full bg-elder-ink" />
              <div
                className="absolute bottom-1/2 left-1/2 h-10 w-1 -translate-x-1/2 origin-bottom rounded-full bg-elder-ink"
                style={{ transform: `translateX(-50%) rotate(${hourRotation}deg)` }}
              />
              <div
                className="absolute bottom-1/2 left-1/2 h-14 w-0.5 -translate-x-1/2 origin-bottom rounded-full bg-elder-moss"
                style={{ transform: `translateX(-50%) rotate(${minuteRotation}deg)` }}
              />
              <div className="absolute inset-3 rounded-full border border-dashed border-elder-sand/70" />
            </div>
          </div>

          <input
            type="range"
            min={0}
            max={MINUTES_PER_DAY - 1}
            step={1}
            value={simulatedMinutes}
            onChange={(event) => setSimulatedMinutes(Number(event.target.value))}
            className="mt-6 w-full accent-elder-moss"
          />

          <div className="mt-3 flex items-center justify-between text-sm text-elder-ink/55">
            <span>00:00</span>
            <span>{formatMinuteLabel(simulatedMinutes)}</span>
            <span>23:59</span>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={() => setClockRunning((current) => !current)}
              className="rounded-full bg-elder-moss px-5 py-3 text-base text-white transition hover:opacity-90"
            >
              {clockRunning ? '暂停走时' : '开始走时'}
            </button>
            <button
              type="button"
              onClick={() => setSimulatedMinutes((current) => Math.max(0, current - 30))}
              className="rounded-full border border-elder-sand/80 bg-white/80 px-5 py-3 text-base text-elder-ink transition hover:bg-white"
            >
              回退 30 分钟
            </button>
            <button
              type="button"
              onClick={() => setSimulatedMinutes((current) => Math.min(MINUTES_PER_DAY - 1, current + 30))}
              className="rounded-full border border-elder-sand/80 bg-white/80 px-5 py-3 text-base text-elder-ink transition hover:bg-white"
            >
              前进 30 分钟
            </button>
            <button
              type="button"
              onClick={() => {
                setClockRunning(false);
                setSimulatedMinutes(getMinutesFromDate(new Date()));
                setReminderFeed([]);
              }}
              className="rounded-full border border-elder-sand/80 bg-white/80 px-5 py-3 text-base text-elder-ink transition hover:bg-white"
            >
              回到现在
            </button>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-2">
            <span className="text-sm text-elder-ink/60">走时速度</span>
            {CLOCK_SPEED_OPTIONS.map((speed) => (
              <button
                key={speed}
                type="button"
                onClick={() => setClockStepMinutes(speed)}
                className={`rounded-full px-4 py-2 text-sm transition ${
                  clockStepMinutes === speed
                    ? 'bg-elder-ink text-white'
                    : 'border border-elder-sand/80 bg-white/80 text-elder-ink hover:bg-white'
                }`}
              >
                {speed} 分钟/秒
              </button>
            ))}
          </div>
        </div>

        <div className="mt-8 w-full rounded-[34px] border border-white/60 bg-[var(--card)] p-6 shadow-lg sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xl font-semibold text-elder-moss sm:text-2xl">自动提醒记录</p>
              <p className="mt-2 text-base text-elder-ink/65 sm:text-lg">当模拟时间跨过服药、通知或留言时间，会自动出现在这里，并尝试语音播报。</p>
            </div>
          </div>
          <div className="mt-5 space-y-3">
            {reminderFeed.length === 0 ? <p className="text-lg text-elder-ink/55">当前还没有新的自动提醒触发。</p> : null}
            {reminderFeed.map((item) => (
              <div key={item.id} className="rounded-3xl border border-elder-sand/70 bg-white/85 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <p className="text-lg font-semibold text-elder-ink">{item.title}</p>
                  <span className="rounded-full bg-elder-sand/40 px-3 py-1 text-sm text-elder-ink/70">{item.simulated_at}</span>
                </div>
                <p className="mt-2 text-lg leading-relaxed text-elder-ink/80">{item.detail}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-8 w-full rounded-[34px] border border-white/60 bg-[var(--card)] p-6 shadow-lg sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <p className="text-xl font-semibold text-elder-moss sm:text-2xl">文字输入</p>
              <p className="mt-2 text-base text-elder-ink/65 sm:text-lg">不方便说话时，可以直接输入。按 Enter 发送，Shift + Enter 换行。</p>
            </div>
            <button
              type="button"
              onClick={submitTypedText}
              disabled={state === 'thinking' || !typedInput.trim()}
              className="rounded-full bg-elder-moss px-6 py-3 text-lg text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {state === 'thinking' ? '发送中…' : '发送文字'}
            </button>
          </div>
          <textarea
            value={typedInput}
            onChange={(event) => setTypedInput(event.target.value)}
            onKeyDown={(event) => {
              void handleTypedInputKeyDown(event);
            }}
            className="mt-4 min-h-28 w-full rounded-3xl border border-elder-sand/70 bg-white/90 px-5 py-4 text-xl leading-relaxed text-elder-ink outline-none focus:border-elder-moss sm:text-2xl"
            placeholder="例如：我今天午饭十二点十分才吃，晚饭想晚一点。"
          />
        </div>
      </div>
    </main>
  );
}
