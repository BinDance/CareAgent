from __future__ import annotations

import re
from datetime import datetime
from dateutil.parser import isoparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from agent_core.provider.llm import LLMProvider
from agent_core.schemas.common import CognitionDecision
from agent_core.tools.base import ToolExecutor


BREAKFAST_TRIGGER_DELAY_MINUTES = 15
BREAKFAST_TRIGGER_TOLERANCE_MINUTES = 14


def _profile_timezone(profile: dict[str, object]) -> ZoneInfo | None:
    timezone_name = str(profile.get('timezone') or '').strip()
    if not timezone_name:
        return None
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None


def _parse_clock(value: object) -> int | None:
    text = str(value or '').strip()
    if not text:
        return None
    match = re.search(r'(?P<hour>\d{1,2})[:：](?P<minute>\d{1,2})', text)
    if match:
        hour = int(match.group('hour'))
        minute = int(match.group('minute'))
    else:
        chinese_match = re.search(r'(?P<hour>\d{1,2})\s*点(?:(?P<half>半)|(?P<minute>\d{1,2})\s*分?)?', text)
        if not chinese_match:
            return None
        hour = int(chinese_match.group('hour'))
        minute = 30 if chinese_match.group('half') else int(chinese_match.group('minute') or 0)
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _breakfast_minutes(profile: dict[str, object], daily_status: dict[str, object]) -> int:
    stable_profile = profile.get('stable_profile') if isinstance(profile.get('stable_profile'), dict) else {}
    stable_profile = stable_profile or {}
    candidates = [
        daily_status.get('breakfast_at'),
        daily_status.get('today_breakfast_time'),
        stable_profile.get('usual_breakfast_time'),
        stable_profile.get('breakfast_time'),
    ]
    for candidate in candidates:
        minutes = _parse_clock(candidate)
        if minutes is not None:
            return minutes
    return 7 * 60 + 30


def _has_generated_today(history: list[dict[str, object]], now_local: datetime) -> bool:
    for item in history:
        if item.get('status') != 'generated':
            continue
        created_at = item.get('created_at')
        try:
            created_dt = datetime.fromisoformat(str(created_at))
        except ValueError:
            continue
        if created_dt.tzinfo is None:
            created_local = created_dt
        else:
            created_local = created_dt.astimezone(now_local.tzinfo)
        if created_local.date() == now_local.date():
            return True
    return False


def _scheduler_gate(profile: dict[str, object], daily_status: dict[str, object], history: list[dict[str, object]], trigger: str, now_ts: str | None = None) -> tuple[bool, str]:
    if trigger != 'scheduler':
        return True, ''
    tz = _profile_timezone(profile)
    if now_ts:
        parsed = isoparse(str(now_ts))
        if tz and parsed.tzinfo:
            now_local = parsed.astimezone(tz)
        elif tz:
            now_local = parsed.replace(tzinfo=tz)
        else:
            now_local = parsed
    else:
        now_local = datetime.now(tz) if tz else datetime.now()
    if _has_generated_today(history, now_local):
        return False, '今日早餐后认知互动已完成。'
    breakfast_minutes = _breakfast_minutes(profile, daily_status)
    trigger_minutes = breakfast_minutes + BREAKFAST_TRIGGER_DELAY_MINUTES
    end_minutes = trigger_minutes + BREAKFAST_TRIGGER_TOLERANCE_MINUTES
    now_minutes = now_local.hour * 60 + now_local.minute
    if trigger_minutes <= now_minutes <= end_minutes:
        return True, ''
    trigger_time = f'{(trigger_minutes // 60) % 24:02d}:{trigger_minutes % 60:02d}'
    end_time = f'{(end_minutes // 60) % 24:02d}:{end_minutes % 60:02d}'
    return False, f'当前不在早餐后15分钟触发时间窗（{trigger_time}-{end_time}）。'


async def load_profile(state: dict[str, str], tools: ToolExecutor) -> dict[str, object]:
    return {'profile': await tools.call('get_elder_profile', {'elder_id': state['elder_id']})}


async def load_status(state: dict[str, str], tools: ToolExecutor) -> dict[str, object]:
    return {'daily_status': await tools.call('get_today_status', {'elder_id': state['elder_id']})}


async def load_history(state: dict[str, str], tools: ToolExecutor) -> dict[str, object]:
    return {'history': await tools.call('get_cognition_history', {'elder_id': state['elder_id']})}


async def decide_interaction(state: dict[str, object], llm: LLMProvider) -> dict[str, object]:
    profile = state.get('profile', {})
    daily_status = state.get('daily_status', {})
    history = state.get('history', [])
    allowed, rationale = _scheduler_gate(profile, daily_status, history, str(state.get('trigger', 'scheduler')), state.get('now_ts'))
    if not allowed:
        return {
            'decision': CognitionDecision(should_engage=False, rationale=rationale),
            'skip_persist': True,
        }
    decision = await llm.decide_cognition({'profile': profile, 'daily_status': daily_status, 'history': history, 'now_ts': state.get('now_ts')})
    if str(state.get('trigger', 'scheduler')) == 'scheduler':
        decision.should_engage = True
        decision.theme = '早餐后工作回忆'
        decision.prompt = '李阿姨，想听您说说以前的工作。您那时候最拿手、最有成就感的一件事是什么？'
        decision.observation_focus = decision.observation_focus or '早餐后回忆表达的流畅度与工作相关记忆提取'
        decision.rationale = '依据今日画像里的早餐时间，向后推15分钟自动触发。' if not decision.rationale else f'依据今日画像里的早餐时间，向后推15分钟自动触发。{decision.rationale}'
    return {'decision': decision, 'skip_persist': False}


async def persist_session(state: dict[str, object], tools: ToolExecutor) -> dict[str, object]:
    if state.get('skip_persist'):
        return {'saved_result': {}}
    decision = state['decision']
    payload = {
        'trigger': state.get('trigger', 'scheduler'),
        'should_engage': decision.should_engage,
        'theme': decision.theme,
        'prompt': decision.prompt,
        'observation_focus': decision.observation_focus,
        'rationale': decision.rationale,
        'anomaly_signal': decision.anomaly_signal,
        'generated_at': state.get('now_ts') or datetime.utcnow().isoformat(),
    }
    result = await tools.call('save_cognition_session', {'elder_id': state['elder_id'], 'result_json': payload})
    if decision.anomaly_signal:
        await tools.call('request_human_review', {'task_type': 'cognition_signal', 'payload': payload})
    return {'saved_result': result}
