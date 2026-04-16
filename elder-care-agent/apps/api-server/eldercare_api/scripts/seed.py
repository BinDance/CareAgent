from __future__ import annotations

import os
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from eldercare_api.database import Base, SessionLocal, engine
from eldercare_api.models import (
    Alert,
    CognitionSession,
    Conversation,
    DailyStatus,
    Elder,
    ElderProfile,
    FamilyMember,
    FamilyMessage,
    FamilyNotice,
    MedicationLog,
    MedicationPlan,
    Prescription,
    ReviewQueue,
    User,
)

ELDER_ID = 'elder-demo-1'
ELDER_USER_ID = 'user-elder-1'
FAMILY_USER_ID = 'user-family-1'
FAMILY_MEMBER_ID = 'family-member-1'


def _reset_tables(db: Session) -> None:
    for model in [MedicationLog, MedicationPlan, Prescription, FamilyMessage, FamilyNotice, Conversation, CognitionSession, Alert, ReviewQueue, DailyStatus, ElderProfile, FamilyMember, Elder, User]:
        db.execute(delete(model))
    db.commit()


def seed_demo_data(db: Session) -> None:
    _reset_tables(db)

    elder_user = User(id=ELDER_USER_ID, email='elder@example.com', display_name='李阿姨', role='elder', access_token='demo-elder-token')
    family_user = User(id=FAMILY_USER_ID, email='family@example.com', display_name='王女士', role='family', access_token='demo-family-token')
    db.add_all([elder_user, family_user])
    db.commit()

    elder = Elder(id=ELDER_ID, user_id=ELDER_USER_ID, name='李阿姨', timezone='Asia/Shanghai', birth_year=1947, voice_locale='zh-CN')
    family = FamilyMember(id=FAMILY_MEMBER_ID, user_id=FAMILY_USER_ID, elder_id=ELDER_ID, relationship_label='daughter', preferred_name='王女士')
    db.add_all([elder, family])
    db.commit()

    profile = ElderProfile(
        elder_id=ELDER_ID,
        stable_profile_json={
            'usual_wake_time': '06:50',
            'usual_sleep_time': '21:20',
            'usual_breakfast_time': '07:20',
            'usual_lunch_time': '12:00',
            'usual_dinner_time': '17:40',
            'chronic_conditions': ['高血压', '失眠'],
            'allergies': [],
            'meal_habits': ['早餐清淡', '晚饭较早'],
            'liked_topics': ['家人近况', '种花', '以前的工作'],
            'disliked_topics': ['考试式提问'],
            'frequently_mentioned_people': ['儿子', '女儿'],
            'reminder_preference': 'gentle',
        },
        risk_profile_json={
            'forgetfulness_trend': 'mild',
            'low_mood_trend': 'stable',
            'medication_refusal_trend': 'none',
            'routine_disruption_trend': 'none',
            'high_risk_expression': 'none',
        },
    )
    daily = DailyStatus(
        elder_id=ELDER_ID,
        status_date=date.today(),
        status_json={
            'plan': ['上午散步', '午饭后休息', '晚上和家人通话'],
            'mood': 'calm',
            'mood_summary': '今天整体平稳，愿意聊天。',
            'went_out': True,
            'medication_taken': False,
            'contacted_people': ['女儿'],
            'is_resting': False,
        },
        family_report_json={
            'date': date.today().isoformat(),
            'mood_summary': '今天整体平稳，上午提到想给儿子带话。',
            'medication_summary': {'taken': False, 'reminders_sent': 0},
        },
    )
    db.add_all([profile, daily])
    db.commit()

    conversations = [
        Conversation(elder_id=ELDER_ID, speaker='elder', content='我今天早上出去走了走，天气还不错。', summary_json={'mood': 'positive'}),
        Conversation(elder_id=ELDER_ID, speaker='agent', content='出去走走挺好，回来记得喝点水。', summary_json={'tone': 'gentle'}),
        Conversation(elder_id=ELDER_ID, speaker='elder', content='中午别忘了提醒我吃药。', summary_json={'intent': 'medication'}),
    ]
    db.add_all(conversations)
    db.commit()

    db.commit()


def seed_demo_data_if_empty() -> bool:
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        existing_user = db.scalar(select(User.id).limit(1))
        if existing_user:
            return False
        try:
            seed_demo_data(db)
        except Exception:
            db.rollback()
            raise
        return True


def main() -> None:
    Base.metadata.create_all(bind=engine)
    reset = os.getenv('DEMO_SEED_RESET', 'false').lower() == 'true'
    with SessionLocal() as db:
        try:
            if reset:
                seed_demo_data(db)
                print('seeded elder care demo data (reset)')
                return
            existing_user = db.scalar(select(User.id).limit(1))
            if existing_user:
                print('demo data already present, skipping seed')
                return
            seed_demo_data(db)
        except Exception:
            db.rollback()
            raise
    print('seeded elder care demo data')


if __name__ == '__main__':
    main()
