export type NoticeUrgency = "low" | "medium" | "high" | "critical";

export type DeliveryStrategy =
  | "now"
  | "next_free_slot"
  | "before_meal"
  | "after_nap"
  | "evening"
  | "manual_review";

export type MessageDirection = "elder_to_family" | "family_to_elder";

export interface MoodSummary {
  label: string;
  confidence: number;
  summary: string;
}

export interface DashboardCardItem {
  title: string;
  value: string;
  tone?: "neutral" | "good" | "warning" | "danger";
}

export interface MedicationPlanSummary {
  id: string;
  medicationName: string;
  dose: string;
  schedule: string;
  status: string;
}

export interface FamilyMessageItem {
  id: string;
  direction: MessageDirection;
  content: string;
  summary?: string;
  createdAt: string;
  deliveredAt?: string | null;
}
