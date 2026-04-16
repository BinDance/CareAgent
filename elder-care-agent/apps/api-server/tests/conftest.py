from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT / 'apps' / 'api-server'))
sys.path.append(str(ROOT / 'packages' / 'agent-core'))

os.environ['APP_ENV'] = 'test'
os.environ['ELDERCARE_AUTH_OPTIONAL'] = 'true'

from agent_core.provider.llm import LLMProvider
from agent_core.runtime import AgentRuntime
from agent_core.tools.local_mcp import LocalToolExecutor
from eldercare_api.database import Base, get_db
from eldercare_api.deps import get_agent_runtime
from eldercare_api.main import create_app
from eldercare_api.scripts.seed import seed_demo_data
from eldercare_api.services.domain_service import DomainService


@pytest.fixture()
def app_client(tmp_path):
    db_path = tmp_path / 'test.db'
    os.environ['DATABASE_URL'] = f'sqlite+pysqlite:///{db_path}'
    engine = create_engine(os.environ['DATABASE_URL'], future=True)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)
    Base.metadata.create_all(bind=engine)
    with TestingSessionLocal() as db:
        seed_demo_data(db)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    def build_handlers():
        def handler(method_name: str):
            def _inner(**kwargs):
                with TestingSessionLocal() as db:
                    return getattr(DomainService(db), method_name)(**kwargs)
            return _inner
        return {name: handler(name) for name in [
            'get_elder_profile',
            'propose_profile_update',
            'get_today_status',
            'update_today_status',
            'get_recent_conversations',
            'create_family_notice',
            'list_pending_notices',
            'mark_notice_delivered',
            'reschedule_notice',
            'create_medication_plan',
            'get_due_medications',
            'log_medication_reminder',
            'confirm_medication_taken',
            'send_message_to_family',
            'list_family_messages',
            'send_message_to_elder',
            'mark_family_message_delivered',
            'get_cognition_history',
            'save_cognition_session',
            'generate_daily_report',
            'publish_report_to_family',
            'raise_alert',
            'request_human_review',
            'save_conversation',
        ]}

    runtime = AgentRuntime(llm=LLMProvider(), tools=LocalToolExecutor(build_handlers()))
    app = create_app(start_scheduler=False)
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_agent_runtime] = lambda: runtime
    with TestClient(app) as client:
        yield client
