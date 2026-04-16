'use client';

import { startTransition, useEffect, useState, type ChangeEvent } from 'react';

import { Badge, Card, SectionTitle } from '@elder-care/ui';

import {
  createNotice,
  DEFAULT_ELDER_ID,
  deleteNotice,
  createMedicationPlan,
  deleteMedicationPlan,
  getDashboard,
  getDailyReport,
  getMedicationPlans,
  type NoticeItem,
  resetDemoData,
  updateNotice,
  type DashboardResult,
  updateMedicationPlan,
  uploadPrescription,
  type MedicationPlan
} from '../lib/api';

type DashboardData = DashboardResult;

type PlanFormState = {
  medication_name: string;
  dose: string;
  frequency: string;
  meal_timing: string;
  time_slots_text: string;
  needs_confirmation: boolean;
};

type NoticeFormState = {
  summarized_notice: string;
  urgency: 'low' | 'medium' | 'high' | 'critical';
  delivery_strategy: 'now' | 'next_free_slot' | 'before_meal' | 'after_nap' | 'evening' | 'manual_review';
  rationale: string;
};

const EMPTY_PLAN_FORM: PlanFormState = {
  medication_name: '',
  dose: '',
  frequency: '',
  meal_timing: '',
  time_slots_text: '',
  needs_confirmation: false
};

const EMPTY_NOTICE_FORM: NoticeFormState = {
  summarized_notice: '',
  urgency: 'medium',
  delivery_strategy: 'next_free_slot',
  rationale: '家属手动编辑'
};

function buildPlanForm(plan?: MedicationPlan | null): PlanFormState {
  if (!plan) {
    return EMPTY_PLAN_FORM;
  }
  return {
    medication_name: plan.medication_name || '',
    dose: plan.dose || '',
    frequency: plan.frequency || '',
    meal_timing: plan.meal_timing || '',
    time_slots_text: (plan.time_slots || []).join(', '),
    needs_confirmation: Boolean(plan.needs_confirmation)
  };
}

function buildNoticeForm(notice?: NoticeItem | null): NoticeFormState {
  if (!notice) {
    return EMPTY_NOTICE_FORM;
  }
  return {
    summarized_notice: notice.summarized_notice || '',
    urgency: notice.urgency || 'medium',
    delivery_strategy: notice.delivery_strategy || 'next_free_slot',
    rationale: notice.rationale || '家属手动编辑'
  };
}

function splitTimeSlots(value: string) {
  return value
    .replace(/[，、]/g, ',')
    .split(',')
    .map((item: string) => item.trim())
    .filter(Boolean);
}

function formatLogClock(value?: string | null) {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  }).format(date);
}

function planStatusLabel(plan: MedicationPlan) {
  if (plan.needs_confirmation) {
    return '待家属确认';
  }
  if (plan.status === 'active') {
    return '已启用';
  }
  if (plan.status === 'review') {
    return '待复核';
  }
  return plan.status;
}

function cognitionStatusLabel(status?: string) {
  if (status === 'generated') {
    return '已生成';
  }
  if (status === 'skipped') {
    return '本轮跳过';
  }
  return status || '未知状态';
}

function noticeUrgencyLabel(urgency?: string) {
  const labels: Record<string, string> = {
    low: '低',
    medium: '中',
    high: '高',
    critical: '紧急'
  };
  return labels[urgency || ''] || urgency || '未知';
}

function deliveryStrategyLabel(strategy?: string) {
  const labels: Record<string, string> = {
    now: '立即转达',
    next_free_slot: '老人空闲时',
    before_meal: '饭前',
    after_nap: '午休后',
    evening: '晚上',
    manual_review: '人工复核'
  };
  return labels[strategy || ''] || strategy || '';
}

function ProfileSection({
  title,
  items
}: {
  title: string;
  items: Array<{ key: string; label: string; value: string }>;
}) {
  if (items.length === 0) {
    return null;
  }
  return (
    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <div className="mt-3 space-y-2">
        {items.map((item) => (
          <div key={item.key} className="flex flex-wrap items-start justify-between gap-2 text-sm">
            <span className="text-slate-500">{item.label}</span>
            <span className="max-w-[70%] text-right text-slate-800">{item.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FamilyDashboard() {
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [report, setReport] = useState<any>(null);
  const [medicationPlans, setMedicationPlans] = useState<MedicationPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [noticeBusy, setNoticeBusy] = useState(false);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [planBusy, setPlanBusy] = useState(false);
  const [resetBusy, setResetBusy] = useState(false);
  const [error, setError] = useState('');
  const [actionFeedback, setActionFeedback] = useState('');
  const [noticeFormMode, setNoticeFormMode] = useState<'create' | 'edit'>('create');
  const [editingNoticeId, setEditingNoticeId] = useState<string | null>(null);
  const [noticeForm, setNoticeForm] = useState<NoticeFormState>(EMPTY_NOTICE_FORM);
  const [planFormMode, setPlanFormMode] = useState<'create' | 'edit' | null>(null);
  const [editingPlanId, setEditingPlanId] = useState<string | null>(null);
  const [planForm, setPlanForm] = useState<PlanFormState>(EMPTY_PLAN_FORM);
  const notices = dashboard?.notices || [];
  const medicationLogs = dashboard?.medication_summary?.logs || [];
  const visibleCognitionItems = (dashboard?.cognition_summary?.items || []).filter(
    (item) => item?.status !== 'skipped'
  );
  const latestTakenAtByPlan = new Map<string, string>();

  for (const log of medicationLogs) {
    if (log?.log_type !== 'taken' || !log?.plan_id) {
      continue;
    }
    latestTakenAtByPlan.set(log.plan_id, log.taken_at || log.created_at || '');
  }

  const syncMedicationPlans = (plans: MedicationPlan[]) => {
    setMedicationPlans(plans);
    setDashboard((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        medication_summary: {
          ...current.medication_summary,
          plans
        }
      };
    });
  };

  const loadMedicationPlans = async () => {
    const plansResult = await getMedicationPlans(DEFAULT_ELDER_ID);
    const plans = plansResult.items || [];
    syncMedicationPlans(plans);
    return plans;
  };

  const resetPlanEditor = () => {
    setPlanFormMode(null);
    setEditingPlanId(null);
    setPlanForm(EMPTY_PLAN_FORM);
  };

  const resetNoticeEditor = () => {
    setNoticeFormMode('create');
    setEditingNoticeId(null);
    setNoticeForm(EMPTY_NOTICE_FORM);
  };

  const loadAll = async () => {
    setLoading(true);
    setError('');
    try {
      const [dashboardResult, reportResult, plansResult] = await Promise.all([
        getDashboard(DEFAULT_ELDER_ID),
        getDailyReport(DEFAULT_ELDER_ID),
        getMedicationPlans(DEFAULT_ELDER_ID)
      ]);
      const plans = plansResult.items || dashboardResult.medication_summary?.plans || [];
      setDashboard({
        ...dashboardResult,
        medication_summary: {
          ...dashboardResult.medication_summary,
          plans
        }
      });
      setReport(reportResult.report || null);
      setMedicationPlans(plans);
    } catch (err) {
      setError(err instanceof Error ? err.message : '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAll();
  }, []);

  useEffect(() => {
    const refreshDashboard = () => {
      startTransition(() => {
        void loadAll();
      });
    };
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') {
        refreshDashboard();
      }
    };
    const intervalId = window.setInterval(refreshDashboard, 8000);
    window.addEventListener('focus', refreshDashboard);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener('focus', refreshDashboard);
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, []);

  const refresh = () => {
    startTransition(() => {
      void loadAll();
    });
  };

  const handleEditNotice = (notice: NoticeItem) => {
    setError('');
    setNoticeFormMode('edit');
    setEditingNoticeId(notice.id);
    setNoticeForm(buildNoticeForm(notice));
  };

  const handleSaveNotice = async () => {
    const summary = noticeForm.summarized_notice.trim();
    if (!summary) {
      setError('待传达内容不能为空。');
      return;
    }
    setNoticeBusy(true);
    setActionFeedback('');
    setError('');
    try {
      const savedNotice =
        noticeFormMode === 'edit' && editingNoticeId
          ? await updateNotice(editingNoticeId, {
              summarized_notice: summary,
              urgency: noticeForm.urgency,
              delivery_strategy: noticeForm.delivery_strategy,
              rationale: noticeForm.rationale.trim() || '家属手动编辑'
            })
          : await createNotice({
              elder_id: DEFAULT_ELDER_ID,
              summarized_notice: summary,
              urgency: noticeForm.urgency,
              delivery_strategy: noticeForm.delivery_strategy,
              rationale: noticeForm.rationale.trim() || '家属手动编辑'
            });
      setActionFeedback((noticeFormMode === 'edit' ? '已更新待传达事项：' : '已新增待传达事项：') + savedNotice.summarized_notice);
      resetNoticeEditor();
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '待传达事项保存失败');
    } finally {
      setNoticeBusy(false);
    }
  };

  const handleDeleteExistingNotice = async (notice: NoticeItem) => {
    if (!window.confirm('确认删除这条待传达事项吗？')) {
      return;
    }
    setNoticeBusy(true);
    setActionFeedback('');
    setError('');
    try {
      await deleteNotice(notice.id);
      if (editingNoticeId === notice.id) {
        resetNoticeEditor();
      }
      setActionFeedback('已删除待传达事项。');
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '待传达事项删除失败');
    } finally {
      setNoticeBusy(false);
    }
  };

  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploadBusy(true);
    setActionFeedback('');
    setError('');
    try {
      const result = await uploadPrescription(file);
      const extraction = result.extraction || {};
      const medicationCount = extraction.medications?.length || 0;
      const uncertaintyNotes = extraction.uncertainty_notes || [];
      const overallSummary = extraction.overall_summary || '';
      const needsConfirmation = Boolean(extraction.needs_confirmation);
      if (medicationCount > 0) {
        const suffix = needsConfirmation ? '，但有字段待家属确认。' : '。';
        setActionFeedback('药方已解析，识别到 ' + medicationCount + ' 项药物' + suffix);
      } else if (uncertaintyNotes.length > 0) {
        setActionFeedback('药方上传成功，但暂未稳定识别出药物。' + uncertaintyNotes[0]);
      } else if (overallSummary) {
        setActionFeedback('药方上传成功，但暂未稳定识别出药物。' + overallSummary);
      } else {
        setActionFeedback('药方上传成功，但暂未稳定识别出药物，请换一张更清晰的图片或稍后重试。');
      }
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : '上传失败');
    } finally {
      setUploadBusy(false);
      event.target.value = '';
    }
  };

  const handleCreatePlan = () => {
    setError('');
    setPlanFormMode('create');
    setEditingPlanId(null);
    setPlanForm(buildPlanForm(null));
  };

  const handleEditPlan = (plan: MedicationPlan) => {
    setError('');
    setPlanFormMode('edit');
    setEditingPlanId(plan.id);
    setPlanForm(buildPlanForm(plan));
  };

  const handleSavePlan = async () => {
    const medicationName = planForm.medication_name.trim();
    if (!medicationName) {
      setError('药物名称不能为空。');
      return;
    }
    setPlanBusy(true);
    setActionFeedback('');
    setError('');
    const payload = {
      medication_name: medicationName,
      dose: planForm.dose.trim(),
      frequency: planForm.frequency.trim(),
      meal_timing: planForm.meal_timing.trim(),
      time_slots: splitTimeSlots(planForm.time_slots_text),
      needs_confirmation: planForm.needs_confirmation,
      status: planForm.needs_confirmation ? 'review' as const : 'active' as const
    };
    try {
      const savedPlan =
        planFormMode === 'edit' && editingPlanId
          ? await updateMedicationPlan(editingPlanId, payload)
          : await createMedicationPlan({ elder_id: DEFAULT_ELDER_ID, ...payload });
      await loadMedicationPlans();
      setActionFeedback((planFormMode === 'edit' ? '已更新服药计划：' : '已新增服药计划：') + savedPlan.medication_name);
      resetPlanEditor();
    } catch (err) {
      setError(err instanceof Error ? err.message : '服药计划保存失败');
    } finally {
      setPlanBusy(false);
    }
  };

  const handleDeletePlan = async (plan: MedicationPlan) => {
    if (!window.confirm('确认删除“' + plan.medication_name + '”这条服药计划吗？')) {
      return;
    }
    setPlanBusy(true);
    setActionFeedback('');
    setError('');
    try {
      await deleteMedicationPlan(plan.id);
      await loadMedicationPlans();
      if (editingPlanId === plan.id) {
        resetPlanEditor();
      }
      setActionFeedback('已删除服药计划：' + plan.medication_name);
    } catch (err) {
      setError(err instanceof Error ? err.message : '服药计划删除失败');
    } finally {
      setPlanBusy(false);
    }
  };

  const handleResetDemo = async () => {
    if (!window.confirm('确认将当前演示数据恢复到初始状态吗？这会清空你刚才的药方和手动修改。')) {
      return;
    }
    setResetBusy(true);
    setActionFeedback('');
    setError('');
    try {
      const result = await resetDemoData();
      resetNoticeEditor();
      resetPlanEditor();
      setActionFeedback('演示数据已恢复初始状态。已清理上传文件 ' + result.cleared_uploads + ' 个。');
      await loadAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : '演示数据重置失败');
    } finally {
      setResetBusy(false);
    }
  };

  const pairedCardClass = 'bg-white/95 h-full';
  const fullWidthCardClass = 'bg-white/95 xl:col-span-2';

  return (
    <main className="min-h-screen px-4 py-6 sm:px-8 sm:py-10">
      <div className="mx-auto max-w-7xl space-y-6">
        <section className="rounded-[36px] border border-white/60 bg-white/40 p-6 shadow-xl backdrop-blur-md sm:p-8">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <SectionTitle
              eyebrow="Family Console"
              title={dashboard ? dashboard.elder_name + ' 的今日陪护总览' : '家属端总览'}
              subtitle="待传达事项、药方、风险和日内状态都在这里统一查看。"
            />
            <button
              type="button"
              onClick={handleResetDemo}
              disabled={resetBusy}
              className="rounded-full border border-rose-200 bg-white/90 px-5 py-3 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {resetBusy ? '正在恢复初始状态…' : '恢复演示初始状态'}
            </button>
          </div>
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {(dashboard?.cards || []).map((card) => (
              <Card key={card.title} className="bg-white/95">
                <p className="text-sm uppercase tracking-[0.18em] text-slate-500">{card.title}</p>
                <p className="mt-3 text-3xl font-semibold text-family-ink">{card.value}</p>
                <div className="mt-4">
                  <Badge tone={card.tone || 'neutral'}>{card.tone || 'neutral'}</Badge>
                </div>
              </Card>
            ))}
          </div>
        </section>

        {loading ? <Card title="加载中">正在获取仪表盘数据…</Card> : null}
        {error ? <Card title="错误"><p className="text-rose-700">{error}</p></Card> : null}
        {actionFeedback ? <Card title="最新操作"><p className="text-emerald-700">{actionFeedback}</p></Card> : null}

        <div className="grid gap-6 xl:grid-cols-2">
          <Card title="长期画像" className={pairedCardClass}>
            <div className="space-y-3">
              <p className="text-sm text-slate-600">长期稳定信息，用于兜底作息、偏好和健康背景。</p>
              <ProfileSection title="长期作息" items={dashboard?.profile_summary?.long_term_profile?.routine || []} />
              <ProfileSection title="偏好与习惯" items={dashboard?.profile_summary?.long_term_profile?.preferences || []} />
              <ProfileSection title="疾病与过敏" items={dashboard?.profile_summary?.long_term_profile?.health || []} />
              <ProfileSection title="风险画像" items={dashboard?.profile_summary?.long_term_profile?.risk || []} />
            </div>
          </Card>

          <Card title="今日画像" className={pairedCardClass}>
            <div className="space-y-3">
              <p className="text-sm text-slate-600">{dashboard?.profile_summary?.today_profile?.fallback_note || '今日未记录字段会自动沿用长期画像。'}</p>

              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <p className="text-sm font-semibold text-slate-900">今日有效作息</p>
                <div className="mt-3 space-y-2">
                  {(dashboard?.profile_summary?.today_profile?.effective_routine || []).map((item) => (
                    <div key={item.key} className="flex flex-wrap items-center justify-between gap-2 text-sm">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-slate-500">{item.label}</span>
                        <Badge tone={item.source === 'today' ? 'good' : 'neutral'}>
                          {item.source === 'today' ? '今日' : '长期'}
                        </Badge>
                      </div>
                      <span className="text-slate-800">{item.value}</span>
                    </div>
                  ))}
                </div>
              </div>

              <ProfileSection title="今日已知作息" items={dashboard?.profile_summary?.today_profile?.observed_updates || []} />
              <ProfileSection title="今日状态" items={dashboard?.profile_summary?.today_profile?.status || []} />
            </div>
          </Card>

          <Card title="待传达 / 已计划事项" className={fullWidthCardClass}>
            <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
              <div className="space-y-4 rounded-3xl border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{noticeFormMode === 'edit' ? '编辑事项' : '新增事项'}</p>
                    <p className="mt-1 text-sm text-slate-500">直接手动维护待传达内容和计划时机。</p>
                  </div>
                  {noticeFormMode === 'edit' ? (
                    <button
                      type="button"
                      onClick={resetNoticeEditor}
                      disabled={noticeBusy}
                      className="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-600 transition hover:bg-white disabled:opacity-60"
                    >
                      取消编辑
                    </button>
                  ) : null}
                </div>
                <textarea
                  value={noticeForm.summarized_notice}
                  onChange={(event) => setNoticeForm((current) => ({ ...current, summarized_notice: event.target.value }))}
                  className="min-h-28 w-full rounded-3xl border border-slate-200 bg-white px-4 py-4 text-base outline-none focus:border-family-teal"
                  placeholder="例如：请您现在下楼拿一下东西。"
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <label className="space-y-2 text-sm text-slate-600">
                    <span>紧急程度</span>
                    <select
                      value={noticeForm.urgency}
                      onChange={(event) => setNoticeForm((current) => ({ ...current, urgency: event.target.value as NoticeFormState['urgency'] }))}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none focus:border-family-teal"
                    >
                      <option value="low">低</option>
                      <option value="medium">中</option>
                      <option value="high">高</option>
                      <option value="critical">紧急</option>
                    </select>
                  </label>
                  <label className="space-y-2 text-sm text-slate-600">
                    <span>传达时机</span>
                    <select
                      value={noticeForm.delivery_strategy}
                      onChange={(event) => setNoticeForm((current) => ({ ...current, delivery_strategy: event.target.value as NoticeFormState['delivery_strategy'] }))}
                      className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 outline-none focus:border-family-teal"
                    >
                      <option value="now">立即转达</option>
                      <option value="next_free_slot">老人空闲时</option>
                      <option value="before_meal">饭前</option>
                      <option value="after_nap">午休后</option>
                      <option value="evening">晚上</option>
                      <option value="manual_review">人工复核</option>
                    </select>
                  </label>
                </div>
                <input
                  value={noticeForm.rationale}
                  onChange={(event) => setNoticeForm((current) => ({ ...current, rationale: event.target.value }))}
                  className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-family-teal"
                  placeholder="备注，例如：家属手动编辑"
                />
                <button
                  type="button"
                  onClick={handleSaveNotice}
                  disabled={noticeBusy}
                  className="rounded-full bg-family-ink px-6 py-3 text-white transition hover:opacity-90 disabled:opacity-60"
                >
                  {noticeBusy ? '保存中…' : noticeFormMode === 'edit' ? '保存修改' : '新增事项'}
                </button>
              </div>

              <div className="space-y-3">
                {notices.length === 0 ? <p className="text-slate-600">当前还没有待传达事项。</p> : null}
                {notices.map((item) => (
                  <div key={item.id} className="rounded-3xl border border-slate-200 bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={item.urgency === 'critical' || item.urgency === 'high' ? 'danger' : item.urgency === 'medium' ? 'warning' : 'neutral'}>
                          {noticeUrgencyLabel(item.urgency)}
                        </Badge>
                        <span className="text-sm text-slate-500">{deliveryStrategyLabel(item.delivery_strategy)}</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => handleEditNotice(item)}
                          disabled={noticeBusy}
                          className="rounded-full border border-slate-200 px-3 py-1.5 text-sm text-slate-700 transition hover:bg-slate-50 disabled:opacity-60"
                        >
                          编辑
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteExistingNotice(item)}
                          disabled={noticeBusy}
                          className="rounded-full border border-rose-200 px-3 py-1.5 text-sm text-rose-700 transition hover:bg-rose-50 disabled:opacity-60"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                    <p className="mt-3 text-slate-900">{item.summarized_notice}</p>
                    <p className="mt-2 text-sm text-slate-500">{item.suitable_window}</p>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card title="医生药方上传" className={pairedCardClass}>
            <p className="text-sm text-slate-600">支持图片或 PDF。系统会先做多模态理解，再把不确定字段标记为待确认。</p>
            <label className="mt-4 flex cursor-pointer items-center justify-between rounded-3xl border border-dashed border-family-gold bg-family-warm px-5 py-6 text-slate-700">
              <span>{uploadBusy ? '正在解析药方…' : '选择药方图片或 PDF'}</span>
              <span className="rounded-full bg-white px-4 py-2 text-sm font-medium">上传</span>
              <input type="file" accept="image/*,.pdf" onChange={handleUpload} className="hidden" />
            </label>
            <p className="mt-3 text-sm text-slate-500">高风险或不完整字段不会静默自动执行。</p>
          </Card>

          <Card title="风险提示" className={pairedCardClass}>
            <div className="space-y-3">
              {(dashboard?.risk_alerts || []).length === 0 ? <p className="text-slate-600">当前没有未处理的高风险告警。</p> : null}
              {(dashboard?.risk_alerts || []).map((item) => (
                <div key={item.id} className="rounded-3xl border border-rose-200 bg-rose-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <Badge tone="danger">{item.level}</Badge>
                    <span className="text-sm text-slate-500">{item.created_at}</span>
                  </div>
                  <p className="mt-3 text-slate-800">{item.reason}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card title="今日日报" className={pairedCardClass}>
            <div className="space-y-4 text-sm leading-7 text-slate-700">
              <p><strong>心情：</strong>{report?.mood_summary || dashboard?.today_mood_summary?.summary || '暂无'}</p>
              <p><strong>服药：</strong>{report?.medication_summary?.taken ? '今天已有服药确认。' : '今天还没有明确的服药确认。'}</p>
              <p><strong>声明：</strong>{report?.disclaimer || '本系统不是医疗诊断工具。'}</p>
            </div>
          </Card>

          <Card title="轻度认知互动记录" className={pairedCardClass}>
            <div className="space-y-3">
              {visibleCognitionItems.length === 0 ? <p className="text-slate-600">当前没有需要展示的认知互动记录。</p> : null}
              {visibleCognitionItems.map((item) => (
                <div key={item.id} className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                  <p className="text-base font-semibold text-slate-900">{item.theme || '轻度互动'}</p>
                  <p className="mt-2 text-sm text-slate-600">{item.prompt}</p>
                  <p className="mt-2 text-xs tracking-[0.2em] text-slate-400">{cognitionStatusLabel(item.status)}</p>
                </div>
              ))}
            </div>
          </Card>

          <Card title="服药计划概览" className={fullWidthCardClass}>
            <div className="space-y-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-slate-600">支持前端手动新增、编辑和删除服药计划。</p>
                <button
                  type="button"
                  onClick={handleCreatePlan}
                  disabled={planBusy}
                  className="rounded-full border border-family-teal/30 px-4 py-2 text-sm font-medium text-family-teal transition hover:bg-family-teal/5 disabled:opacity-60"
                >
                  新增计划
                </button>
              </div>

              {planFormMode ? (
                <div className="rounded-3xl border border-family-teal/20 bg-family-warm p-4">
                  <p className="text-sm font-semibold text-slate-900">{planFormMode === 'edit' ? '编辑服药计划' : '新增服药计划'}</p>
                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <input
                      value={planForm.medication_name}
                      onChange={(event) => setPlanForm((current) => ({ ...current, medication_name: event.target.value }))}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-family-teal"
                      placeholder="药物名称，例如：阿司匹林"
                    />
                    <input
                      value={planForm.dose}
                      onChange={(event) => setPlanForm((current) => ({ ...current, dose: event.target.value }))}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-family-teal"
                      placeholder="剂量，例如：100mg"
                    />
                    <input
                      value={planForm.frequency}
                      onChange={(event) => setPlanForm((current) => ({ ...current, frequency: event.target.value }))}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-family-teal"
                      placeholder="频次，例如：每日 2 次"
                    />
                    <input
                      value={planForm.meal_timing}
                      onChange={(event) => setPlanForm((current) => ({ ...current, meal_timing: event.target.value }))}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-family-teal"
                      placeholder="服用时机，例如：饭后"
                    />
                  </div>
                  <input
                    value={planForm.time_slots_text}
                    onChange={(event) => setPlanForm((current) => ({ ...current, time_slots_text: event.target.value }))}
                    className="mt-3 w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none focus:border-family-teal"
                    placeholder="提醒时段，多个用逗号分隔，例如：08:00, 20:00"
                  />
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <label className="flex items-center gap-2 text-sm text-slate-600">
                      <input
                        type="checkbox"
                        checked={planForm.needs_confirmation}
                        onChange={(event) => setPlanForm((current) => ({ ...current, needs_confirmation: event.target.checked }))}
                        className="h-4 w-4 rounded border-slate-300 text-family-teal focus:ring-family-teal"
                      />
                      保存为待确认计划
                    </label>
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={resetPlanEditor}
                        disabled={planBusy}
                        className="rounded-full border border-slate-200 px-4 py-2 text-sm text-slate-600 transition hover:bg-white disabled:opacity-60"
                      >
                        取消
                      </button>
                      <button
                        type="button"
                        onClick={handleSavePlan}
                        disabled={planBusy}
                        className="rounded-full bg-family-teal px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-60"
                      >
                        {planBusy ? '保存中…' : '保存计划'}
                      </button>
                    </div>
                  </div>
                </div>
              ) : null}

              <div className="grid gap-3 xl:grid-cols-2">
                {medicationPlans.length === 0 ? <p className="text-sm text-slate-600">当前还没有服药计划。</p> : null}
                {medicationPlans.map((plan) => {
                  const takenAt = latestTakenAtByPlan.get(plan.id);
                  return (
                    <div key={plan.id} className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="text-lg font-semibold text-slate-900">{plan.medication_name}</p>
                            <Badge tone={plan.needs_confirmation ? 'warning' : 'good'}>{planStatusLabel(plan)}</Badge>
                            {takenAt ? <Badge tone="good">今日已服</Badge> : null}
                          </div>
                          <p className="mt-2 text-sm text-slate-600">
                            {[plan.dose, plan.frequency, plan.meal_timing].filter(Boolean).join(' / ') || '剂量与服用方式待补充'}
                          </p>
                          <p className="mt-1 text-sm text-slate-500">提醒时段：{(plan.time_slots || []).join('、') || '待定'}</p>
                          {takenAt ? <p className="mt-1 text-sm text-emerald-700">今日服药：已确认 {formatLogClock(takenAt)}</p> : null}
                          {plan.start_date || plan.end_date ? (
                            <p className="mt-1 text-sm text-slate-500">
                              生效日期：{plan.start_date || '即日'} 至 {plan.end_date || '长期'}
                            </p>
                          ) : null}
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={() => handleEditPlan(plan)}
                            disabled={planBusy}
                            className="rounded-full border border-slate-200 px-3 py-1.5 text-sm text-slate-700 transition hover:bg-white disabled:opacity-60"
                          >
                            编辑
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeletePlan(plan)}
                            disabled={planBusy}
                            className="rounded-full border border-rose-200 px-3 py-1.5 text-sm text-rose-700 transition hover:bg-rose-50 disabled:opacity-60"
                          >
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>
        </div>
      </div>
    </main>
  );
}
