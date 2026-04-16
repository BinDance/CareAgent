from __future__ import annotations

from typing import Any

from eldercare_api.services.domain_service import DomainService


class PrescriptionService:
    def __init__(self, domain: DomainService):
        self.domain = domain

    def create_record(self, elder_id: str, file_name: str, file_path: str, mime_type: str, uploaded_by_user_id: str | None) -> dict[str, Any]:
        return self.domain.create_prescription_record(elder_id, file_name, file_path, mime_type, uploaded_by_user_id)

    def finalize_record(self, prescription_id: str, extraction: dict[str, Any], needs_confirmation: bool) -> dict[str, Any] | None:
        return self.domain.finalize_prescription_record(prescription_id, extraction, needs_confirmation)
