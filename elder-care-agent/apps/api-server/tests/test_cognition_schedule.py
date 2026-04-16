from datetime import datetime
from zoneinfo import ZoneInfo

from agent_core.graphs.cognition_care import nodes as cognition_nodes
from agent_core.schemas.common import CognitionDecision


def _set_now(monkeypatch, year: int, month: int, day: int, hour: int, minute: int):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            base = datetime(year, month, day, hour, minute, tzinfo=ZoneInfo('Asia/Shanghai'))
            if tz is None:
                return base.replace(tzinfo=None)
            return base.astimezone(tz)

    monkeypatch.setattr(cognition_nodes, 'datetime', FixedDateTime)


def test_scheduler_gate_allows_once_in_breakfast_window(monkeypatch):
    _set_now(monkeypatch, 2026, 4, 16, 7, 45)
    profile = {'timezone': 'Asia/Shanghai', 'stable_profile': {'usual_breakfast_time': '07:20'}}
    allowed, rationale = cognition_nodes._scheduler_gate(profile, {}, [], 'scheduler')

    assert allowed is True
    assert rationale == ''


def test_scheduler_gate_uses_today_breakfast_time(monkeypatch):
    _set_now(monkeypatch, 2026, 4, 16, 13, 20)
    profile = {'timezone': 'Asia/Shanghai', 'stable_profile': {'usual_breakfast_time': '07:20'}}
    daily_status = {'breakfast_at': '13:00'}
    allowed, rationale = cognition_nodes._scheduler_gate(profile, daily_status, [], 'scheduler')

    assert allowed is True
    assert rationale == ''


def test_scheduler_gate_blocks_outside_breakfast_window(monkeypatch):
    _set_now(monkeypatch, 2026, 4, 16, 10, 30)
    profile = {'timezone': 'Asia/Shanghai', 'stable_profile': {'usual_breakfast_time': '07:20'}}
    allowed, rationale = cognition_nodes._scheduler_gate(profile, {}, [], 'scheduler')

    assert allowed is False
    assert '早餐后15分钟触发时间窗' in rationale


def test_scheduler_gate_blocks_after_generated_today(monkeypatch):
    _set_now(monkeypatch, 2026, 4, 16, 7, 50)
    profile = {'timezone': 'Asia/Shanghai', 'stable_profile': {'usual_breakfast_time': '07:20'}}
    history = [
        {
            'status': 'generated',
            'created_at': '2026-04-16T07:40:00+08:00',
        }
    ]

    allowed, rationale = cognition_nodes._scheduler_gate(profile, {}, history, 'scheduler')

    assert allowed is False
    assert rationale == '今日早餐后认知互动已完成。'


def test_scheduler_decision_forces_breakfast_prompt(monkeypatch):
    _set_now(monkeypatch, 2026, 4, 16, 7, 45)

    class FakeLLM:
        async def decide_cognition(self, _context):
            return CognitionDecision(should_engage=False, rationale='模型原本想跳过。')

    result = cognition_nodes.decide_interaction(
        {
            'profile': {'timezone': 'Asia/Shanghai', 'stable_profile': {'usual_breakfast_time': '07:20'}},
            'daily_status': {},
            'history': [],
            'trigger': 'scheduler',
            'now_ts': '2026-04-16T07:45:00+08:00',
        },
        FakeLLM(),
    )

    import asyncio
    output = asyncio.run(result)

    assert output['decision'].should_engage is True
    assert '向后推15分钟自动触发' in output['decision'].rationale
    assert output['skip_persist'] is False
