from __future__ import annotations

from functools import lru_cache

from agent_core import AgentRuntime
from agent_core.provider.llm import LLMProvider
from agent_core.tools.local_mcp import LocalToolExecutor
from agent_core.tools.remote_mcp import RemoteMCPToolExecutor
from eldercare_api.config import get_settings
from eldercare_api.database import SessionLocal
from eldercare_api.services.domain_service import DomainService


def _build_local_handlers() -> dict[str, object]:
    def handler(method_name: str):
        def _inner(**kwargs):
            with SessionLocal() as db:
                return getattr(DomainService(db), method_name)(**kwargs)
        return _inner

    names = [
        'get_elder_profile',
        'propose_profile_update',
        'get_today_status',
        'update_today_status',
        'get_recent_conversations',
        'create_family_notice',
        'list_pending_notices',
        'mark_notice_delivered',
        'reschedule_notice',
        'create_medication_plan',
        'get_due_medications',
        'log_medication_reminder',
        'confirm_medication_taken',
        'send_message_to_family',
        'list_family_messages',
        'send_message_to_elder',
        'mark_family_message_delivered',
        'get_cognition_history',
        'save_cognition_session',
        'generate_daily_report',
        'publish_report_to_family',
        'raise_alert',
        'request_human_review',
        'save_conversation',
    ]
    return {name: handler(name) for name in names}


@lru_cache(maxsize=1)
def get_agent_runtime() -> AgentRuntime:
    settings = get_settings()
    llm = LLMProvider()
    if settings.app_env == 'production':
        return AgentRuntime(llm=llm, tools=RemoteMCPToolExecutor())
    return AgentRuntime(llm=llm, tools=LocalToolExecutor(_build_local_handlers()))
