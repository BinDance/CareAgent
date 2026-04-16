from __future__ import annotations

from sqlalchemy.orm import Session

from eldercare_api.models import Prescription


class PrescriptionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, **kwargs) -> Prescription:
        prescription = Prescription(**kwargs)
        self.db.add(prescription)
        self.db.flush()
        return prescription

    def get(self, prescription_id: str) -> Prescription | None:
        return self.db.get(Prescription, prescription_id)
