from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from eldercare_api.auth import require_elder_user
from eldercare_api.database import get_db
from eldercare_api.deps import get_agent_runtime
from eldercare_api.services.scheduler_service import SchedulerService
from eldercare_api.schemas import ElderSessionResponse, ElderVoiceInputRequest, ElderVoiceInputResponse, TodayRemindersResponse, UserContext
from eldercare_api.services.domain_service import DomainService

router = APIRouter(prefix='/api/elder', tags=['elder'])


@router.post('/voice-input', response_model=ElderVoiceInputResponse)
async def elder_voice_input(
    payload: ElderVoiceInputRequest,
    current_user: UserContext = Depends(require_elder_user),
    runtime=Depends(get_agent_runtime),
    db: Session = Depends(get_db),
) -> ElderVoiceInputResponse:
    if current_user.elder_id and current_user.elder_id != payload.elder_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='elder mismatch')
    if payload.now_ts:
        await SchedulerService(DomainService(db)).run_notice_scheduler(now_ts=payload.now_ts)
    state = await runtime.run_elder_conversation(payload.elder_id, payload.transcript, now_ts=payload.now_ts)
    response = state['response']
    mood_signal = state['mood_signal']
    risk_signal = state['risk_signal']
    return ElderVoiceInputResponse(
        elder_id=payload.elder_id,
        transcript=payload.transcript,
        reply_text=response.reply_text,
        subtitle=response.subtitle,
        should_speak=response.should_speak,
        mood=mood_signal.label,
        risk_level=risk_signal.level,
        delivered_notice_ids=response.deliver_notice_ids,
        reminder_plan_ids=response.reminder_plan_ids,
    )


@router.get('/session/{elder_id}', response_model=ElderSessionResponse)
def elder_session(
    elder_id: str,
    current_user: UserContext = Depends(require_elder_user),
    db: Session = Depends(get_db),
) -> ElderSessionResponse:
    if current_user.elder_id and current_user.elder_id != elder_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='elder mismatch')
    service = DomainService(db)
    return ElderSessionResponse(**service.get_elder_session(elder_id))


@router.get('/today-reminders', response_model=TodayRemindersResponse)
async def today_reminders(
    elder_id: str | None = Query(default=None),
    now_ts: str | None = Query(default=None),
    since_ts: str | None = Query(default=None),
    current_user: UserContext = Depends(require_elder_user),
    db: Session = Depends(get_db),
    runtime=Depends(get_agent_runtime),
) -> TodayRemindersResponse:
    resolved_elder_id = elder_id or current_user.elder_id
    if not resolved_elder_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='missing elder_id')
    if current_user.elder_id and current_user.elder_id != resolved_elder_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='elder mismatch')
    service = DomainService(db)
    if now_ts:
        await SchedulerService(service).run_notice_scheduler(now_ts=now_ts)
    reminders = service.get_today_reminders(resolved_elder_id, now_ts=now_ts, since_ts=since_ts)
    cognition: list[dict[str, Any]] = []
    if now_ts:
        state = await runtime.run_cognition_care(resolved_elder_id, 'scheduler', now_ts=now_ts)
        saved_result = state.get('saved_result') or {}
        if saved_result:
            cognition.append(saved_result)
    return TodayRemindersResponse(**reminders, cognition=cognition)
