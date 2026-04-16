from __future__ import annotations

import os
from typing import Any

os.environ.setdefault('FASTMCP_CHECK_FOR_UPDATES', 'off')

from fastmcp import FastMCP

from eldercare_api.database import SessionLocal
from eldercare_api.services.domain_service import DomainService

mcp = FastMCP('elder-care-tools')


def with_service(fn):
    with SessionLocal() as db:
        service = DomainService(db)
        return fn(service)


@mcp.tool()
def get_elder_profile(elder_id: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.get_elder_profile(elder_id))


@mcp.tool()
def propose_profile_update(elder_id: str, candidate_json: dict[str, Any]) -> dict[str, Any]:
    return with_service(lambda svc: svc.propose_profile_update(elder_id, candidate_json))


@mcp.tool()
def get_today_status(elder_id: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.get_today_status(elder_id))


@mcp.tool()
def update_today_status(elder_id: str, patch_json: dict[str, Any]) -> dict[str, Any]:
    return with_service(lambda svc: svc.update_today_status(elder_id, patch_json))


@mcp.tool()
def get_recent_conversations(elder_id: str, limit: int = 10) -> list[dict[str, Any]]:
    return with_service(lambda svc: svc.get_recent_conversations(elder_id, limit))


@mcp.tool()
def save_conversation(elder_id: str, speaker: str, content: str, summary_json: dict[str, Any]) -> dict[str, Any]:
    return with_service(lambda svc: svc.save_conversation(elder_id, speaker, content, summary_json))


@mcp.tool()
def create_family_notice(elder_id: str, raw_text: str, urgency: str, strategy: str, summarized_notice: str, rationale: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.create_family_notice(elder_id, raw_text, urgency, strategy, summarized_notice, rationale))


@mcp.tool()
def list_pending_notices(elder_id: str) -> list[dict[str, Any]]:
    return with_service(lambda svc: svc.list_pending_notices(elder_id))


@mcp.tool()
def mark_notice_delivered(notice_id: str, delivered_at: str) -> dict[str, Any] | None:
    return with_service(lambda svc: svc.mark_notice_delivered(notice_id, delivered_at))


@mcp.tool()
def reschedule_notice(notice_id: str, new_slot: str) -> dict[str, Any] | None:
    return with_service(lambda svc: svc.reschedule_notice(notice_id, new_slot))


@mcp.tool()
def create_medication_plan(elder_id: str, medication_json: dict[str, Any]) -> dict[str, Any]:
    return with_service(lambda svc: svc.create_medication_plan(elder_id, medication_json))


@mcp.tool()
def get_due_medications(elder_id: str, now_ts: str) -> list[dict[str, Any]]:
    return with_service(lambda svc: svc.get_due_medications(elder_id, now_ts))


@mcp.tool()
def log_medication_reminder(plan_id: str, scheduled_at: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.log_medication_reminder(plan_id, scheduled_at))


@mcp.tool()
def confirm_medication_taken(plan_id: str, taken_at: str, source: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.confirm_medication_taken(plan_id, taken_at, source))


@mcp.tool()
def send_message_to_family(elder_id: str, summary_text: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.send_message_to_family(elder_id, summary_text))


@mcp.tool()
def list_family_messages(elder_id: str) -> list[dict[str, Any]]:
    return with_service(lambda svc: svc.list_family_messages(elder_id))


@mcp.tool()
def send_message_to_elder(elder_id: str, text: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.send_message_to_elder(elder_id, text))


@mcp.tool()
def mark_family_message_delivered(message_id: str, delivered_at: str) -> dict[str, Any] | None:
    return with_service(lambda svc: svc.mark_family_message_delivered(message_id, delivered_at))


@mcp.tool()
def get_cognition_history(elder_id: str) -> list[dict[str, Any]]:
    return with_service(lambda svc: svc.get_cognition_history(elder_id))


@mcp.tool()
def save_cognition_session(elder_id: str, result_json: dict[str, Any]) -> dict[str, Any]:
    return with_service(lambda svc: svc.save_cognition_session(elder_id, result_json))


@mcp.tool()
def generate_daily_report(elder_id: str, date: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.generate_daily_report(elder_id, date))


@mcp.tool()
def publish_report_to_family(elder_id: str, report_json: dict[str, Any]) -> dict[str, Any]:
    return with_service(lambda svc: svc.publish_report_to_family(elder_id, report_json))


@mcp.tool()
def raise_alert(elder_id: str, reason: str, level: str) -> dict[str, Any]:
    return with_service(lambda svc: svc.raise_alert(elder_id, reason, level))


@mcp.tool()
def request_human_review(task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    return with_service(lambda svc: svc.request_human_review(task_type, payload))


if __name__ == '__main__':
    mcp.run(transport='http', host='0.0.0.0', port=9000, path='/mcp')
