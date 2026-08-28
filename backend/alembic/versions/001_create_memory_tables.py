"""create memory tables

Revision ID: 001_create_memory_tables
Revises: 
Create Date: 2026-08-02

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '001_create_memory_tables'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.create_table(
        'memories',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('memory_type', sa.String(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('importance', sa.Integer(), nullable=False),
        sa.Column('is_pinned', sa.Boolean(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('structured_data', sa.JSON(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_memories_id'), 'memories', ['id'], unique=False)
    op.create_index(op.f('ix_memories_title'), 'memories', ['title'], unique=False)
    op.create_index(op.f('ix_memories_memory_type'), 'memories', ['memory_type'], unique=False)
    op.create_index(op.f('ix_memories_category'), 'memories', ['category'], unique=False)
    op.create_index(op.f('ix_memories_importance'), 'memories', ['importance'], unique=False)
    op.create_index(op.f('ix_memories_is_pinned'), 'memories', ['is_pinned'], unique=False)
    op.create_index(op.f('ix_memories_source'), 'memories', ['source'], unique=False)
    op.create_index(op.f('ix_memories_deleted_at'), 'memories', ['deleted_at'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_memories_deleted_at'), table_name='memories')
    op.drop_index(op.f('ix_memories_source'), table_name='memories')
    op.drop_index(op.f('ix_memories_is_pinned'), table_name='memories')
    op.drop_index(op.f('ix_memories_importance'), table_name='memories')
    op.drop_index(op.f('ix_memories_category'), table_name='memories')
    op.drop_index(op.f('ix_memories_memory_type'), table_name='memories')
    op.drop_index(op.f('ix_memories_title'), table_name='memories')
    op.drop_index(op.f('ix_memories_id'), table_name='memories')
    op.drop_table('memories')
