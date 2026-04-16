from __future__ import annotations

from typing import Any, TypedDict

from agent_core.schemas.common import PrescriptionExtraction


class PrescriptionState(TypedDict, total=False):
    elder_id: str
    file_path: str
    file_name: str
    mime_type: str
    image_urls: list[str]
    supporting_text: str
    extraction: PrescriptionExtraction
    created_plans: list[dict[str, Any]]
    review_item: dict[str, Any]
