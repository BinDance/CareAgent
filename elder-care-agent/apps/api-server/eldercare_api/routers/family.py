from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from eldercare_api.auth import require_family_user
from eldercare_api.config import get_settings
from eldercare_api.database import get_db
from eldercare_api.deps import get_agent_runtime
from eldercare_api.schemas import (
    DailyReportResponse,
    DashboardResponse,
    DemoResetResponse,
    FamilyInstructionResponse,
    FamilyMessageCreateRequest,
    FamilyMessagesResponse,
    ManualNoticeCreateRequest,
    ManualNoticeResponse,
    ManualNoticeUpdateRequest,
    MedicationPlanCreateRequest,
    MedicationPlanResponse,
    MedicationPlansResponse,
    MedicationPlanUpdateRequest,
    FamilyNoticeRequest,
    UploadPrescriptionResponse,
    UserContext,
)
from eldercare_api.scripts.seed import ELDER_ID, seed_demo_data
from eldercare_api.services.domain_service import DomainService
from eldercare_api.services.prescription_service import PrescriptionService
from eldercare_api.utils.files import clear_uploads, save_upload

router = APIRouter(prefix='/api/family', tags=['family'])


@router.post('/demo-reset', response_model=DemoResetResponse)
def reset_demo_data(
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> DemoResetResponse:
    settings = get_settings()
    if settings.app_env == 'production':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='demo reset is disabled in production')
    cleared_uploads = clear_uploads()
    seed_demo_data(db)
    return DemoResetResponse(
        detail='demo data reset',
        elder_id=ELDER_ID,
        cleared_uploads=cleared_uploads,
    )


@router.post('/notice', response_model=FamilyInstructionResponse)
async def create_family_notice(
    payload: FamilyNoticeRequest,
    _: UserContext = Depends(require_family_user),
    runtime=Depends(get_agent_runtime),
) -> FamilyInstructionResponse:
    state = await runtime.run_family_instruction(payload.elder_id, payload.text)
    result = state['result']
    persisted = state.get('persisted_result', {})
    return FamilyInstructionResponse(
        elder_id=payload.elder_id,
        kind=result.kind,
        summary=result.summarized_notice,
        urgency=result.urgency,
        delivery_strategy=result.delivery_strategy,
        suitable_window=result.suitable_window,
        rationale=result.rationale,
        stored_notice=persisted.get('notice'),
        relay_message=persisted.get('message'),
        query=persisted.get('query'),
        review=persisted.get('review'),
    )


@router.post('/notices', response_model=ManualNoticeResponse)
def create_manual_notice(
    payload: ManualNoticeCreateRequest,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> ManualNoticeResponse:
    service = DomainService(db)
    notice = service.create_family_notice(
        elder_id=payload.elder_id,
        raw_text=payload.summarized_notice,
        urgency=payload.urgency,
        strategy=payload.delivery_strategy,
        summarized_notice=payload.summarized_notice,
        rationale=payload.rationale,
    )
    return ManualNoticeResponse(**notice)


@router.patch('/notices/{notice_id}', response_model=ManualNoticeResponse)
def update_manual_notice(
    notice_id: str,
    payload: ManualNoticeUpdateRequest,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> ManualNoticeResponse:
    service = DomainService(db)
    notice = service.update_family_notice(notice_id, payload.model_dump(exclude_unset=True))
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='notice not found')
    return ManualNoticeResponse(**notice)


@router.delete('/notices/{notice_id}')
def delete_manual_notice(
    notice_id: str,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = DomainService(db)
    notice = service.delete_family_notice(notice_id)
    if notice is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='notice not found')
    return {'detail': 'deleted', 'notice_id': notice_id}


@router.post('/upload-prescription', response_model=UploadPrescriptionResponse)
async def upload_prescription(
    elder_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
    runtime=Depends(get_agent_runtime),
) -> UploadPrescriptionResponse:
    path = await save_upload(file)
    domain = DomainService(db)
    record_service = PrescriptionService(domain)
    record = record_service.create_record(
        elder_id=elder_id,
        file_name=file.filename or path.name,
        file_path=str(path),
        mime_type=file.content_type or 'application/octet-stream',
        uploaded_by_user_id=current_user.user_id,
    )
    state = await runtime.run_prescription(elder_id, str(path), file.filename or path.name, file.content_type or 'application/octet-stream')
    extraction_model = state['extraction']
    extraction = extraction_model.model_dump() if hasattr(extraction_model, 'model_dump') else extraction_model
    finalized = record_service.finalize_record(record['id'], extraction, extraction.get('needs_confirmation', False))
    if finalized is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail='failed to finalize prescription')
    return UploadPrescriptionResponse(
        prescription_id=finalized['id'],
        parse_status=finalized['parse_status'],
        extraction=extraction,
        created_plans=state.get('created_plans', []),
        review_item=state.get('review_item'),
    )


@router.get('/dashboard/{elder_id}', response_model=DashboardResponse)
def family_dashboard(
    elder_id: str,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> DashboardResponse:
    service = DomainService(db)
    return DashboardResponse(**service.get_dashboard(elder_id))


@router.get('/medication-plans/{elder_id}', response_model=MedicationPlansResponse)
def family_medication_plans(
    elder_id: str,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> MedicationPlansResponse:
    service = DomainService(db)
    return MedicationPlansResponse(elder_id=elder_id, items=service.list_medication_plans(elder_id))


@router.post('/medication-plans', response_model=MedicationPlanResponse)
def create_medication_plan(
    payload: MedicationPlanCreateRequest,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> MedicationPlanResponse:
    service = DomainService(db)
    plan = service.create_medication_plan(payload.elder_id, payload.model_dump())
    return MedicationPlanResponse(**plan)


@router.patch('/medication-plans/{plan_id}', response_model=MedicationPlanResponse)
def update_medication_plan(
    plan_id: str,
    payload: MedicationPlanUpdateRequest,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> MedicationPlanResponse:
    service = DomainService(db)
    plan = service.update_medication_plan(plan_id, payload.model_dump(exclude_unset=True))
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='medication plan not found')
    return MedicationPlanResponse(**plan)


@router.delete('/medication-plans/{plan_id}')
def delete_medication_plan(
    plan_id: str,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    service = DomainService(db)
    plan = service.delete_medication_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='medication plan not found')
    return {'detail': 'deleted', 'plan_id': plan_id}


@router.get('/messages/{elder_id}', response_model=FamilyMessagesResponse)
def family_messages(
    elder_id: str,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> FamilyMessagesResponse:
    service = DomainService(db)
    return FamilyMessagesResponse(elder_id=elder_id, items=service.list_family_messages(elder_id))


@router.post('/message-to-elder')
async def message_to_elder(
    payload: FamilyMessageCreateRequest,
    _: UserContext = Depends(require_family_user),
    runtime=Depends(get_agent_runtime),
) -> dict[str, Any]:
    state = await runtime.run_family_relay(payload.elder_id, 'family', payload.text)
    relay = state['relay']
    result = state['result']
    return {
        'elder_id': payload.elder_id,
        'relay': relay.model_dump() if hasattr(relay, 'model_dump') else relay,
        'result': result,
    }


@router.get('/reports/daily/{elder_id}', response_model=DailyReportResponse)
def daily_report(
    elder_id: str,
    _: UserContext = Depends(require_family_user),
    db: Session = Depends(get_db),
) -> DailyReportResponse:
    service = DomainService(db)
    report = service.generate_daily_report(elder_id, __import__('datetime').date.today().isoformat())
    service.publish_report_to_family(elder_id, report)
    return DailyReportResponse(elder_id=elder_id, date=report['date'], report=report)
