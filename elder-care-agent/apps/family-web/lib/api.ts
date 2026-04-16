const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
const DEMO_FAMILY_TOKEN = process.env.NEXT_PUBLIC_FAMILY_DEMO_TOKEN || 'demo-family-token';
export const DEFAULT_ELDER_ID = 'elder-demo-1';

export type MedicationPlan = {
  id: string;
  elder_id: string;
  prescription_id?: string | null;
  medication_name: string;
  dose: string;
  frequency: string;
  meal_timing: string;
  time_slots: string[];
  start_date?: string | null;
  end_date?: string | null;
  confidence: number;
  needs_confirmation: boolean;
  status: string;
  created_at: string;
};

export type DashboardProfileItem = {
  key: string;
  label: string;
  value: string;
};

export type DashboardEffectiveRoutineItem = DashboardProfileItem & {
  source: 'today' | 'long_term';
};

export type DashboardResult = {
  elder_id: string;
  elder_name: string;
  cards: Array<{ title: string; value: string; tone?: 'neutral' | 'good' | 'warning' | 'danger' }>;
  today_mood_summary: { mood: string; summary: string };
  medication_summary: { plans: MedicationPlan[]; logs: Array<any> };
  notices: Array<any>;
  messages: Array<any>;
  cognition_summary: { items: Array<any> };
  risk_alerts: Array<any>;
  profile_summary?: {
    long_term_profile: {
      routine: DashboardProfileItem[];
      preferences: DashboardProfileItem[];
      health: DashboardProfileItem[];
      risk: DashboardProfileItem[];
    };
    today_profile: {
      fallback_note: string;
      effective_routine: DashboardEffectiveRoutineItem[];
      observed_updates: DashboardProfileItem[];
      status: DashboardProfileItem[];
    };
  };
  daily_report: Record<string, any>;
};

export type NoticeItem = {
  id: string;
  elder_id: string;
  raw_text: string;
  summarized_notice: string;
  urgency: 'low' | 'medium' | 'high' | 'critical';
  delivery_strategy: 'now' | 'next_free_slot' | 'before_meal' | 'after_nap' | 'evening' | 'manual_review';
  suitable_window?: string | null;
  rationale: string;
  status: string;
  planned_for?: string | null;
  delivered_at?: string | null;
  created_at: string;
};

export type UploadPrescriptionResult = {
  prescription_id: string;
  parse_status: string;
  extraction: {
    medications: Array<{
      medication_name: string;
      dose: string;
      frequency: string;
      meal_timing: string;
      suggested_times: string[];
      start_date: string | null;
      end_date: string | null;
      confidence: number;
      uncertain_fields: string[];
    }>;
    overall_summary?: string;
    uncertainty_notes?: string[];
    needs_confirmation?: boolean;
    raw_observations?: string[];
  };
  created_plans: Array<{
    id: string;
    medication_name: string;
    dose: string;
    frequency: string;
    meal_timing: string;
    time_slots: string[];
    confidence: number;
    needs_confirmation: boolean;
    status: string;
    created_at: string;
  }>;
  review_item?: {
    id: string;
    task_type: string;
    status: string;
    priority: string;
  } | null;
};

export type MedicationPlansResult = {
  elder_id: string;
  items: MedicationPlan[];
};

export type DemoResetResult = {
  ok: boolean;
  detail: string;
  elder_id: string;
  cleared_uploads: number;
};

function withAuthHeaders(headers: HeadersInit = {}) {
  return {
    ...headers,
    Authorization: `Bearer ${DEMO_FAMILY_TOKEN}`
  };
}

async function parseJson(response: Response) {
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || '请求失败');
  }
  return response.json();
}

export async function getDashboard(elderId = DEFAULT_ELDER_ID) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/dashboard/' + elderId, {
      cache: 'no-store',
      headers: withAuthHeaders()
    })
  ) as Promise<DashboardResult>;
}

export async function getMessages(elderId = DEFAULT_ELDER_ID) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/messages/' + elderId, {
      cache: 'no-store',
      headers: withAuthHeaders()
    })
  );
}

export async function getDailyReport(elderId = DEFAULT_ELDER_ID) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/reports/daily/' + elderId, {
      cache: 'no-store',
      headers: withAuthHeaders()
    })
  );
}

export async function createNotice(
  payload: {
    elder_id: string;
    summarized_notice: string;
    urgency: 'low' | 'medium' | 'high' | 'critical';
    delivery_strategy: 'now' | 'next_free_slot' | 'before_meal' | 'after_nap' | 'evening' | 'manual_review';
    rationale?: string;
  }
) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/notices', {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    })
  ) as Promise<NoticeItem>;
}

export async function updateNotice(
  noticeId: string,
  payload: {
    summarized_notice?: string;
    urgency?: 'low' | 'medium' | 'high' | 'critical';
    delivery_strategy?: 'now' | 'next_free_slot' | 'before_meal' | 'after_nap' | 'evening' | 'manual_review';
    rationale?: string;
  }
) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/notices/' + noticeId, {
      method: 'PATCH',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    })
  ) as Promise<NoticeItem>;
}

export async function deleteNotice(noticeId: string) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/notices/' + noticeId, {
      method: 'DELETE',
      headers: withAuthHeaders()
    })
  ) as Promise<{ detail: string; notice_id: string }>;
}

export async function sendMessageToElder(text: string, elderId = DEFAULT_ELDER_ID) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/message-to-elder', {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ elder_id: elderId, text })
    })
  );
}

export async function uploadPrescription(file: File, elderId = DEFAULT_ELDER_ID) {
  const formData = new FormData();
  formData.append('elder_id', elderId);
  formData.append('file', file);
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/upload-prescription', {
      method: 'POST',
      headers: withAuthHeaders(),
      body: formData
    })
  ) as Promise<UploadPrescriptionResult>;
}

export async function getMedicationPlans(elderId = DEFAULT_ELDER_ID) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/medication-plans/' + elderId, {
      cache: 'no-store',
      headers: withAuthHeaders()
    })
  ) as Promise<MedicationPlansResult>;
}

export async function createMedicationPlan(
  payload: {
    elder_id: string;
    medication_name: string;
    dose?: string;
    frequency?: string;
    meal_timing?: string;
    time_slots?: string[];
    start_date?: string | null;
    end_date?: string | null;
    needs_confirmation?: boolean;
  }
) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/medication-plans', {
      method: 'POST',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    })
  ) as Promise<MedicationPlan>;
}

export async function updateMedicationPlan(
  planId: string,
  payload: {
    medication_name?: string;
    dose?: string;
    frequency?: string;
    meal_timing?: string;
    time_slots?: string[];
    start_date?: string | null;
    end_date?: string | null;
    needs_confirmation?: boolean;
    status?: 'active' | 'review';
  }
) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/medication-plans/' + planId, {
      method: 'PATCH',
      headers: withAuthHeaders({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(payload)
    })
  ) as Promise<MedicationPlan>;
}

export async function deleteMedicationPlan(planId: string) {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/medication-plans/' + planId, {
      method: 'DELETE',
      headers: withAuthHeaders()
    })
  ) as Promise<{ detail: string; plan_id: string }>;
}

export async function resetDemoData() {
  return parseJson(
    await fetch(API_BASE_URL + '/api/family/demo-reset', {
      method: 'POST',
      headers: withAuthHeaders()
    })
  ) as Promise<DemoResetResult>;
}
