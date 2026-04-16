from __future__ import annotations

from agent_core.provider.file_inputs import prepare_multimodal_payload
from agent_core.provider.llm import LLMProvider
from agent_core.schemas.common import PrescriptionMedicationItem
from agent_core.tools.base import ToolExecutor


async def receive_file(state: dict[str, str]) -> dict[str, str]:
    return {'file_path': state['file_path'], 'file_name': state['file_name'], 'mime_type': state['mime_type']}


async def prepare_payload(state: dict[str, str]) -> dict[str, object]:
    image_urls, supporting_text = prepare_multimodal_payload(state['file_path'])
    return {'image_urls': image_urls, 'supporting_text': supporting_text}


async def parse_multimodal(state: dict[str, object], llm: LLMProvider) -> dict[str, object]:
    extraction = await llm.parse_prescription(str(state.get('supporting_text', '')), list(state.get('image_urls', [])))
    return {'extraction': extraction}


async def risk_check(state: dict[str, object], tools: ToolExecutor) -> dict[str, object]:
    extraction = state['extraction']
    review_item = None
    if extraction.needs_confirmation:
        review_item = await tools.call('request_human_review', {'task_type': 'prescription_review', 'payload': extraction.model_dump()})
    return {'review_item': review_item}


def _should_persist_medication(item: PrescriptionMedicationItem) -> bool:
    name = item.medication_name.strip()
    if not name:
        return False
    has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in name)
    has_instruction = any([item.dose, item.frequency, item.meal_timing, item.start_date, item.end_date])
    if item.confidence < 0.45:
        return False
    if not has_instruction and not has_cjk:
        return False
    return True


async def persist_plan(state: dict[str, object], tools: ToolExecutor) -> dict[str, object]:
    extraction = state['extraction']
    created_plans = []
    for medication in extraction.medications:
        if not _should_persist_medication(medication):
            continue
        created = await tools.call(
            'create_medication_plan',
            {
                'elder_id': state['elder_id'],
                'medication_json': medication.model_dump() | {'needs_confirmation': extraction.needs_confirmation},
            },
        )
        created_plans.append(created)
    return {'created_plans': created_plans}
