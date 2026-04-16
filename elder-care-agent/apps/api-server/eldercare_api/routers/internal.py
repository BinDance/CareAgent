from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from eldercare_api.config import get_settings
from eldercare_api.database import get_db
from eldercare_api.deps import get_agent_runtime
from eldercare_api.schemas import SchedulerRunResponse
from eldercare_api.services.domain_service import DomainService
from eldercare_api.services.scheduler_service import SchedulerService

router = APIRouter(prefix='/api/internal', tags=['internal'])


def verify_internal(x_internal_token: str | None = Header(default=None)) -> None:
    settings = get_settings()
    if settings.app_env == 'development' and not x_internal_token:
        return
    if x_internal_token != settings.secret_key:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='internal auth failed')


@router.post('/run-notice-scheduler', response_model=SchedulerRunResponse, dependencies=[Depends(verify_internal)])
async def run_notice_scheduler(db: Session = Depends(get_db)) -> SchedulerRunResponse:
    service = SchedulerService(DomainService(db))
    result = await service.run_notice_scheduler()
    return SchedulerRunResponse(processed=result['processed'], details=result['details'])


@router.post('/run-medication-check', response_model=SchedulerRunResponse, dependencies=[Depends(verify_internal)])
async def run_medication_check(db: Session = Depends(get_db)) -> SchedulerRunResponse:
    service = SchedulerService(DomainService(db))
    result = await service.run_medication_check()
    return SchedulerRunResponse(processed=result['processed'], details=result['details'])


@router.post('/run-cognition-check', response_model=SchedulerRunResponse, dependencies=[Depends(verify_internal)])
async def run_cognition_check(db: Session = Depends(get_db), runtime=Depends(get_agent_runtime)) -> SchedulerRunResponse:
    domain = DomainService(db)
    processed = 0
    details: list[dict] = []
    for elder_id in domain.list_elder_ids():
        state = await runtime.run_cognition_care(elder_id, 'scheduler')
        processed += 1
        decision = state['decision']
        details.append({'elder_id': elder_id, 'should_engage': decision.should_engage, 'theme': decision.theme})
    return SchedulerRunResponse(processed=processed, details=details)
