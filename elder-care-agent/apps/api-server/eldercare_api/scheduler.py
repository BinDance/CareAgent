from __future__ import annotations

import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from eldercare_api.config import get_settings
from eldercare_api.database import SessionLocal
from eldercare_api.deps import get_agent_runtime
from eldercare_api.services.domain_service import DomainService
from eldercare_api.services.scheduler_service import SchedulerService

logger = logging.getLogger(__name__)


class AppScheduler:
    def __init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone='Asia/Shanghai')
        self.started = False

    def start(self) -> None:
        if self.started or not get_settings().scheduler_enabled:
            return
        self.scheduler.add_job(self._notice_job, 'interval', minutes=5, id='notice-job', replace_existing=True)
        self.scheduler.add_job(self._medication_job, 'interval', minutes=5, id='medication-job', replace_existing=True)
        self.scheduler.add_job(self._cognition_job, 'interval', minutes=15, id='cognition-job', replace_existing=True)
        self.scheduler.start()
        self.started = True
        logger.info('scheduler started')

    def shutdown(self) -> None:
        if self.started:
            self.scheduler.shutdown(wait=False)
            self.started = False

    async def _notice_job(self) -> None:
        with SessionLocal() as db:
            result = await SchedulerService(DomainService(db)).run_notice_scheduler()
            logger.info('notice scheduler processed %s items', result['processed'])

    async def _medication_job(self) -> None:
        with SessionLocal() as db:
            result = await SchedulerService(DomainService(db)).run_medication_check()
            logger.info('medication scheduler processed %s items', result['processed'])

    async def _cognition_job(self) -> None:
        runtime = get_agent_runtime()
        with SessionLocal() as db:
            domain = DomainService(db)
            count = 0
            for elder_id in domain.list_elder_ids():
                await runtime.run_cognition_care(elder_id, 'scheduler')
                count += 1
            logger.info('cognition scheduler processed %s elders', count)
