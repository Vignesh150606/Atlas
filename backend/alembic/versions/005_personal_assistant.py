"""Phase 10: reminders, tasks, routines tables + memories.expires_at

Revision ID: 005_personal_assistant
Revises: 004_documents_and_entities
Create Date: 2026-08-08 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_personal_assistant'
down_revision: Union[str, None] = '004_documents_and_entities'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Personal Context Engine: temporary-context TTL on Memory -----
    op.add_column('memories', sa.Column('expires_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_memories_expires_at'), 'memories', ['expires_at'], unique=False)

    # --- Reminders -----------------------------------------------------
    op.create_table(
        'reminders',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('due_at', sa.DateTime(), nullable=True),
        sa.Column('raw_when_text', sa.String(), nullable=True),
        sa.Column('timezone', sa.String(), nullable=False, server_default='UTC'),
        sa.Column('recurrence', sa.String(), nullable=False, server_default='none'),
        sa.Column('recurrence_days', sa.JSON(), nullable=False),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('source', sa.String(), nullable=False, server_default='chat'),
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_reminders_due_at'), 'reminders', ['due_at'], unique=False)
    op.create_index(op.f('ix_reminders_recurrence'), 'reminders', ['recurrence'], unique=False)
    op.create_index(op.f('ix_reminders_status'), 'reminders', ['status'], unique=False)
    op.create_index(op.f('ix_reminders_source'), 'reminders', ['source'], unique=False)
    op.create_index(op.f('ix_reminders_conversation_id'), 'reminders', ['conversation_id'], unique=False)

    # --- Tasks -----------------------------------------------------------
    op.create_table(
        'tasks',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(), nullable=False, server_default='pending'),
        sa.Column('priority', sa.String(), nullable=False, server_default='medium'),
        sa.Column('due_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('source', sa.String(), nullable=False, server_default='chat'),
        sa.Column('conversation_id', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tasks_status'), 'tasks', ['status'], unique=False)
    op.create_index(op.f('ix_tasks_priority'), 'tasks', ['priority'], unique=False)
    op.create_index(op.f('ix_tasks_due_at'), 'tasks', ['due_at'], unique=False)
    op.create_index(op.f('ix_tasks_source'), 'tasks', ['source'], unique=False)
    op.create_index(op.f('ix_tasks_conversation_id'), 'tasks', ['conversation_id'], unique=False)

    # --- Routines ----------------------------------------------------------
    op.create_table(
        'routines',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('steps', sa.JSON(), nullable=False),
        sa.Column('time_of_day', sa.String(), nullable=True),
        sa.Column('days_of_week', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_routines_is_active'), 'routines', ['is_active'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_routines_is_active'), table_name='routines')
    op.drop_table('routines')

    op.drop_index(op.f('ix_tasks_conversation_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_source'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_due_at'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_priority'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_status'), table_name='tasks')
    op.drop_table('tasks')

    op.drop_index(op.f('ix_reminders_conversation_id'), table_name='reminders')
    op.drop_index(op.f('ix_reminders_source'), table_name='reminders')
    op.drop_index(op.f('ix_reminders_status'), table_name='reminders')
    op.drop_index(op.f('ix_reminders_recurrence'), table_name='reminders')
    op.drop_index(op.f('ix_reminders_due_at'), table_name='reminders')
    op.drop_table('reminders')

    op.drop_index(op.f('ix_memories_expires_at'), table_name='memories')
    op.drop_column('memories', 'expires_at')
