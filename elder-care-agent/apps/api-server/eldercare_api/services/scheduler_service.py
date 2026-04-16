from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from dateutil.parser import isoparse

from eldercare_api.services.domain_service import DomainService


class SchedulerService:
    def __init__(self, domain: DomainService):
        self.domain = domain

    async def run_notice_scheduler(self, now_ts: str | None = None) -> dict[str, Any]:
        processed = 0
        details: list[dict[str, Any]] = []
        now = isoparse(now_ts) if now_ts else datetime.now(timezone.utc)
        for elder_id in self.domain.list_elder_ids():
            local_now = self.domain._align_to_elder_timezone(elder_id, now.isoformat())
            for notice in self.domain.list_pending_notices(elder_id):
                strategy = notice['delivery_strategy']
                hour = local_now.hour
                should_ready = (
                    strategy == 'now'
                    or (strategy == 'before_meal' and hour in {11, 12, 17, 18})
                    or (strategy == 'after_nap' and hour in {14, 15, 16})
                    or (strategy == 'evening' and hour >= 18)
                    or strategy == 'next_free_slot'
                )
                if should_ready and notice['status'] == 'pending':
                    self.domain.reschedule_notice(notice['id'], now.isoformat())
                    processed += 1
                    details.append({'notice_id': notice['id'], 'elder_id': elder_id, 'action': 'ready_for_delivery'})
        return {'processed': processed, 'details': details}

    async def run_medication_check(self) -> dict[str, Any]:
        processed = 0
        details: list[dict[str, Any]] = []
        now = datetime.now(timezone.utc).isoformat()
        for elder_id in self.domain.list_elder_ids():
            due = self.domain.get_due_medications(elder_id, now)
            for item in due:
                result = self.domain.log_medication_reminder(item['id'], now)
                if result.get('ok', True):
                    processed += 1
                    details.append({'plan_id': item['id'], 'elder_id': elder_id, 'action': 'reminder_logged'})
        return {'processed': processed, 'details': details}
