const API_BASE_URL = '';
const DEFAULT_ELDER_ID = 'elder-demo-1';
const DEMO_ELDER_TOKEN = process.env.NEXT_PUBLIC_ELDER_DEMO_TOKEN || 'demo-elder-token';

export type VoiceReply = {
  elder_id: string;
  transcript: string;
  reply_text: string;
  subtitle: string;
  should_speak: boolean;
  mood: string;
  risk_level: string;
  delivered_notice_ids: string[];
  reminder_plan_ids: string[];
};

export type ElderReminderCognition = {
  id?: string;
  theme?: string | null;
  prompt?: string | null;
  created_at?: string;
};

export type ElderReminderNotice = {
  id: string;
  summarized_notice: string;
  urgency: string;
  suitable_window?: string | null;
  planned_for?: string | null;
  created_at?: string;
};

export type ElderReminderMedication = {
  id: string;
  medication_name: string;
  dose: string;
  frequency: string;
  meal_timing: string;
  time_slots: string[];
};

export type ElderReminderMessage = {
  id: string;
  summary_text: string;
  created_at?: string;
};

export type TodayRemindersResult = {
  elder_id: string;
  notices: ElderReminderNotice[];
  medications: ElderReminderMedication[];
  messages: ElderReminderMessage[];
  cognition: ElderReminderCognition[];
};

export async function sendVoiceInput(
  transcript: string,
  elderId = DEFAULT_ELDER_ID,
  options: {
    nowTs?: string;
  } = {}
): Promise<VoiceReply> {
  const response = await fetch(`${API_BASE_URL}/api/elder/voice-input`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${DEMO_ELDER_TOKEN}`
    },
    body: JSON.stringify({ elder_id: elderId, transcript, now_ts: options.nowTs })
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || '请求失败');
  }

  return response.json();
}

export async function getTodayReminders(
  elderId = DEFAULT_ELDER_ID,
  options: {
    nowTs?: string;
    sinceTs?: string;
  } = {}
): Promise<TodayRemindersResult> {
  const params = new URLSearchParams({ elder_id: elderId });
  if (options.nowTs) {
    params.set('now_ts', options.nowTs);
  }
  if (options.sinceTs) {
    params.set('since_ts', options.sinceTs);
  }

  const response = await fetch(`${API_BASE_URL}/api/elder/today-reminders?${params.toString()}`, {
    headers: {
      Authorization: `Bearer ${DEMO_ELDER_TOKEN}`
    },
    cache: 'no-store'
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || '请求失败');
  }

  return response.json();
}
