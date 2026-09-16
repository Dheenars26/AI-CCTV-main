"""create ppe safety tables

Revision ID: 20260826_ppe_safety
Revises: 20260818_create_phase8_tables
Create Date: 2026-08-26 10:45:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260826_ppe_safety'
down_revision = '20260818_create_phase8_tables'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add new columns to cameras table
    op.add_column('cameras', sa.Column('fire_smoke_enabled', sa.Boolean(), server_default='1', nullable=False))
    op.add_column('cameras', sa.Column('ppe_enabled', sa.Boolean(), server_default='1', nullable=False))
    op.add_column('cameras', sa.Column('person_enabled', sa.Boolean(), server_default='1', nullable=False))
    op.add_column('cameras', sa.Column('zone_enabled', sa.Boolean(), server_default='1', nullable=False))
    op.add_column('cameras', sa.Column('ppe_inference_interval_sec', sa.Float(), server_default='0.5', nullable=False))

    # 2. Create ppe_profiles table
    op.create_table(
        'ppe_profiles',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.String(255), nullable=True),
        sa.Column('required_equipment', sa.JSON(), nullable=False),
        sa.Column('optional_equipment', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_ppe_profiles_name', 'ppe_profiles', ['name'])

    # 3. Create ppe_requirements table
    op.create_table(
        'ppe_requirements',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('ppe_profiles.id', ondelete='CASCADE'), nullable=False),
        sa.Column('equipment_type', sa.String(50), nullable=False),
        sa.Column('is_required', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('severity', sa.String(20), server_default='HIGH', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_ppe_req_profile_equip', 'ppe_requirements', ['profile_id', 'equipment_type'])

    # 4. Create safety_zones table
    op.create_table(
        'safety_zones',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('camera_id', sa.Integer(), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('zone_type', sa.String(30), server_default='HAZARD', nullable=False),
        sa.Column('polygon_coordinates', sa.JSON(), nullable=False),
        sa.Column('ppe_profile_id', sa.Integer(), sa.ForeignKey('ppe_profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('enabled', sa.Boolean(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_safety_zone_cam_type', 'safety_zones', ['camera_id', 'zone_type'])

    # 5. Create person_detections table
    op.create_table(
        'person_detections',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('camera_id', sa.Integer(), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('bounding_box', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_person_dets_cam_time', 'person_detections', ['camera_id', 'timestamp'])
    op.create_index('idx_person_dets_cam_person', 'person_detections', ['camera_id', 'person_id'])

    # 6. Create ppe_violations table
    op.create_table(
        'ppe_violations',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('camera_id', sa.Integer(), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zone_id', sa.Integer(), sa.ForeignKey('safety_zones.id', ondelete='SET NULL'), nullable=True),
        sa.Column('person_id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), sa.ForeignKey('ppe_profiles.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(20), server_default='VIOLATION', nullable=False),
        sa.Column('severity', sa.String(20), server_default='HIGH', nullable=False),
        sa.Column('missing_items', sa.JSON(), nullable=False),
        sa.Column('detected_items', sa.JSON(), nullable=False),
        sa.Column('required_items', sa.JSON(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('evidence_id', sa.String(64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_ppe_viol_cam_time', 'ppe_violations', ['camera_id', 'timestamp'])
    op.create_index('idx_ppe_viol_status_sev', 'ppe_violations', ['status', 'severity'])

    # 7. Create incidents table
    op.create_table(
        'incidents',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('camera_id', sa.Integer(), sa.ForeignKey('cameras.id', ondelete='CASCADE'), nullable=False),
        sa.Column('zone_id', sa.Integer(), sa.ForeignKey('safety_zones.id', ondelete='SET NULL'), nullable=True),
        sa.Column('incident_type', sa.String(50), nullable=False),
        sa.Column('events', sa.JSON(), nullable=False),
        sa.Column('severity', sa.String(20), server_default='HIGH', nullable=False),
        sa.Column('status', sa.String(30), server_default='ACTIVE', nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('evidence_id', sa.String(64), nullable=True),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('cleared_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('idx_incidents_cam_type_status', 'incidents', ['camera_id', 'incident_type', 'status'])
    op.create_index('idx_incidents_sev_start', 'incidents', ['severity', 'start_time'])


def downgrade():
    op.drop_table('incidents')
    op.drop_table('ppe_violations')
    op.drop_table('person_detections')
    op.drop_table('safety_zones')
    op.drop_table('ppe_requirements')
    op.drop_table('ppe_profiles')
    op.drop_column('cameras', 'ppe_inference_interval_sec')
    op.drop_column('cameras', 'zone_enabled')
    op.drop_column('cameras', 'person_enabled')
    op.drop_column('cameras', 'ppe_enabled')
    op.drop_column('cameras', 'fire_smoke_enabled')
