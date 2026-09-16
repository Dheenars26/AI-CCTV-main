"""Create cameras table

Revision ID: 20260817_create_cameras_table
Revises: 
Create Date: 2026-08-17 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '20260817_create_cameras_table'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'cameras',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('camera_number', sa.String(length=50), nullable=False),
        sa.Column('dvr_address', sa.String(length=100), nullable=True),
        sa.Column('rtsp_url', sa.String(length=500), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=False, server_default='rtsp'),
        sa.Column('location', sa.String(length=200), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('fps_limit', sa.Integer(), nullable=False, server_default='25'),
        sa.Column('connection_timeout', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('reconnect_interval', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('cameras')
