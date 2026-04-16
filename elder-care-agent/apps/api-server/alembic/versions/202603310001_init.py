from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '202603310001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False, unique=True),
        sa.Column('display_name', sa.String(length=120), nullable=False),
        sa.Column('role', sa.String(length=32), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=True),
        sa.Column('access_token', sa.String(length=255), nullable=True, unique=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_users_role', 'users', ['role'])

    op.create_table(
        'elders',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False, unique=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('timezone', sa.String(length=64), nullable=False),
        sa.Column('birth_year', sa.Integer(), nullable=True),
        sa.Column('voice_locale', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        'family_members',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('relationship_label', sa.String(length=64), nullable=False),
        sa.Column('preferred_name', sa.String(length=120), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_family_members_elder_id', 'family_members', ['elder_id'])

    op.create_table(
        'elder_profiles',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False, unique=True),
        sa.Column('stable_profile_json', sa.JSON(), nullable=False),
        sa.Column('risk_profile_json', sa.JSON(), nullable=False),
        sa.Column('profile_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_elder_profiles_elder_id', 'elder_profiles', ['elder_id'])

    op.create_table(
        'daily_status',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('status_date', sa.Date(), nullable=False),
        sa.Column('status_json', sa.JSON(), nullable=False),
        sa.Column('family_report_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('elder_id', 'status_date', name='uq_daily_status_elder_date'),
    )
    op.create_index('ix_daily_status_elder_id', 'daily_status', ['elder_id'])
    op.create_index('ix_daily_status_status_date', 'daily_status', ['status_date'])

    op.create_table(
        'family_notices',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('family_member_id', sa.String(length=36), sa.ForeignKey('family_members.id'), nullable=True),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('summarized_notice', sa.Text(), nullable=False),
        sa.Column('urgency', sa.String(length=16), nullable=False),
        sa.Column('delivery_strategy', sa.String(length=32), nullable=False),
        sa.Column('suitable_window', sa.String(length=120), nullable=True),
        sa.Column('rationale', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('planned_for', sa.DateTime(timezone=True), nullable=True),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_family_notices_elder_id', 'family_notices', ['elder_id'])
    op.create_index('ix_family_notices_urgency', 'family_notices', ['urgency'])
    op.create_index('ix_family_notices_status', 'family_notices', ['status'])

    op.create_table(
        'prescriptions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('uploaded_by_user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('mime_type', sa.String(length=120), nullable=False),
        sa.Column('parse_status', sa.String(length=24), nullable=False),
        sa.Column('extracted_json', sa.JSON(), nullable=False),
        sa.Column('uncertainty_notes', sa.JSON(), nullable=False),
        sa.Column('needs_confirmation', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_prescriptions_elder_id', 'prescriptions', ['elder_id'])
    op.create_index('ix_prescriptions_parse_status', 'prescriptions', ['parse_status'])

    op.create_table(
        'medication_plans',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('prescription_id', sa.String(length=36), sa.ForeignKey('prescriptions.id'), nullable=True),
        sa.Column('medication_name', sa.String(length=255), nullable=False),
        sa.Column('dose', sa.String(length=120), nullable=False),
        sa.Column('frequency', sa.String(length=120), nullable=False),
        sa.Column('meal_timing', sa.String(length=64), nullable=False),
        sa.Column('time_slots', sa.JSON(), nullable=False),
        sa.Column('start_date', sa.Date(), nullable=True),
        sa.Column('end_date', sa.Date(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('needs_confirmation', sa.Boolean(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('instructions_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_medication_plans_elder_id', 'medication_plans', ['elder_id'])
    op.create_index('ix_medication_plans_prescription_id', 'medication_plans', ['prescription_id'])
    op.create_index('ix_medication_plans_status', 'medication_plans', ['status'])

    op.create_table(
        'medication_logs',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('plan_id', sa.String(length=36), sa.ForeignKey('medication_plans.id'), nullable=False),
        sa.Column('log_type', sa.String(length=24), nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('taken_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source', sa.String(length=64), nullable=True),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_medication_logs_elder_id', 'medication_logs', ['elder_id'])
    op.create_index('ix_medication_logs_log_type', 'medication_logs', ['log_type'])
    op.create_index('ix_medication_logs_plan_created', 'medication_logs', ['plan_id', 'created_at'])

    op.create_table(
        'conversations',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('speaker', sa.String(length=32), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('summary_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_conversations_elder_id', 'conversations', ['elder_id'])
    op.create_index('ix_conversations_elder_created', 'conversations', ['elder_id', 'created_at'])

    op.create_table(
        'family_messages',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('direction', sa.String(length=32), nullable=False),
        sa.Column('raw_text', sa.Text(), nullable=False),
        sa.Column('summary_text', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('delivered_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_family_messages_direction', 'family_messages', ['direction'])
    op.create_index('ix_family_messages_elder_id', 'family_messages', ['elder_id'])
    op.create_index('ix_family_messages_status', 'family_messages', ['status'])
    op.create_index('ix_family_messages_elder_created', 'family_messages', ['elder_id', 'created_at'])

    op.create_table(
        'cognition_sessions',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('theme', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=True),
        sa.Column('result_json', sa.JSON(), nullable=False),
        sa.Column('anomaly_score', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_cognition_sessions_elder_id', 'cognition_sessions', ['elder_id'])
    op.create_index('ix_cognition_sessions_status', 'cognition_sessions', ['status'])

    op.create_table(
        'alerts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=False),
        sa.Column('reason', sa.Text(), nullable=False),
        sa.Column('level', sa.String(length=16), nullable=False),
        sa.Column('resolved', sa.Boolean(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_alerts_elder_id', 'alerts', ['elder_id'])
    op.create_index('ix_alerts_level', 'alerts', ['level'])

    op.create_table(
        'review_queue',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('elder_id', sa.String(length=36), sa.ForeignKey('elders.id'), nullable=True),
        sa.Column('task_type', sa.String(length=64), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(length=24), nullable=False),
        sa.Column('priority', sa.String(length=16), nullable=False),
        sa.Column('reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_review_queue_elder_id', 'review_queue', ['elder_id'])
    op.create_index('ix_review_queue_task_type', 'review_queue', ['task_type'])
    op.create_index('ix_review_queue_status', 'review_queue', ['status'])


def downgrade() -> None:
    for name in ['review_queue', 'alerts', 'cognition_sessions', 'family_messages', 'conversations', 'medication_logs', 'medication_plans', 'prescriptions', 'family_notices', 'daily_status', 'elder_profiles', 'family_members', 'elders', 'users']:
        op.drop_table(name)
