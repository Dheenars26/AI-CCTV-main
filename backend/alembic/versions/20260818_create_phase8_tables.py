"""Create users, detections, alerts, evidence, notifications, and system_logs tables

Revision ID: 20260818_create_phase8_tables
Revises: 20260817_create_cameras_table
Create Date: 2026-08-18 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '20260818_create_phase8_tables'
down_revision: Union[str, None] = '20260817_create_cameras_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create Users Table
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('username', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=150), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False, server_default='operator'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_superuser', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_username', 'users', ['username'], unique=True)
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. Create Detections Table
    op.create_table(
        'detections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('camera_id', sa.Integer(), nullable=False),
        sa.Column('class_name', sa.String(length=50), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('bounding_box', sa.JSON(), nullable=False),
        sa.Column('frame_number', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('fps', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_detections_camera_id', 'detections', ['camera_id'])
    op.create_index('ix_detections_class_name', 'detections', ['class_name'])
    op.create_index('ix_detections_timestamp', 'detections', ['timestamp'])
    op.create_index('idx_detections_camera_time', 'detections', ['camera_id', 'timestamp'])
    op.create_index('idx_detections_class_conf', 'detections', ['class_name', 'confidence'])

    # 3. Create Alerts Table
    op.create_table(
        'alerts',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('camera_id', sa.Integer(), nullable=False),
        sa.Column('class_name', sa.String(length=50), nullable=False),
        sa.Column('state', sa.String(length=30), nullable=False),
        sa.Column('consecutive_frames', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('duration_seconds', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('max_confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('latest_confidence', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cleared_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_alerts_camera_id', 'alerts', ['camera_id'])
    op.create_index('ix_alerts_class_name', 'alerts', ['class_name'])
    op.create_index('ix_alerts_state', 'alerts', ['state'])
    op.create_index('ix_alerts_start_time', 'alerts', ['start_time'])
    op.create_index('idx_alerts_camera_state', 'alerts', ['camera_id', 'state'])
    op.create_index('idx_alerts_class_start', 'alerts', ['class_name', 'start_time'])

    # 4. Create Evidence Table
    op.create_table(
        'evidence',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('evidence_id', sa.String(length=64), nullable=False),
        sa.Column('alert_id', sa.String(length=36), nullable=False),
        sa.Column('camera_id', sa.Integer(), nullable=False),
        sa.Column('snapshot_relative_path', sa.String(length=500), nullable=False),
        sa.Column('video_relative_path', sa.String(length=500), nullable=True),
        sa.Column('metadata_relative_path', sa.String(length=500), nullable=True),
        sa.Column('file_size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('metadata_envelope', sa.JSON(), nullable=True),
        sa.Column('retention_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['camera_id'], ['cameras.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_evidence_evidence_id', 'evidence', ['evidence_id'], unique=True)
    op.create_index('ix_evidence_alert_id', 'evidence', ['alert_id'])
    op.create_index('ix_evidence_camera_id', 'evidence', ['camera_id'])
    op.create_index('ix_evidence_retention_until', 'evidence', ['retention_until'])
    op.create_index('idx_evidence_camera_retention', 'evidence', ['camera_id', 'retention_until'])

    # 5. Create Notifications Table
    op.create_table(
        'notifications',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('alert_id', sa.String(length=36), nullable=False),
        sa.Column('channel', sa.String(length=30), nullable=False, server_default='email'),
        sa.Column('recipient', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False, server_default='PENDING'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['alert_id'], ['alerts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_notifications_alert_id', 'notifications', ['alert_id'])
    op.create_index('ix_notifications_status', 'notifications', ['status'])
    op.create_index('ix_notifications_sent_at', 'notifications', ['sent_at'])
    op.create_index('idx_notifications_status_time', 'notifications', ['status', 'sent_at'])

    # 6. Create SystemLogs Table
    op.create_table(
        'system_logs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('level', sa.String(length=20), nullable=False, server_default='INFO'),
        sa.Column('module', sa.String(length=100), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('correlation_id', sa.String(length=64), nullable=True),
        sa.Column('camera_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_system_logs_level', 'system_logs', ['level'])
    op.create_index('ix_system_logs_module', 'system_logs', ['module'])
    op.create_index('ix_system_logs_correlation_id', 'system_logs', ['correlation_id'])
    op.create_index('ix_system_logs_camera_id', 'system_logs', ['camera_id'])
    op.create_index('ix_system_logs_created_at', 'system_logs', ['created_at'])
    op.create_index('idx_logs_level_time', 'system_logs', ['level', 'created_at'])


def downgrade() -> None:
    op.drop_table('system_logs')
    op.drop_table('notifications')
    op.drop_table('evidence')
    op.drop_table('alerts')
    op.drop_table('detections')
    op.drop_table('users')
