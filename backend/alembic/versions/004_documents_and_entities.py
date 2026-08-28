"""add documents, entities, entity_relationships tables (Phase 6 - PKS)

Revision ID: 004_documents_and_entities
Revises: 003_memory_lifecycle
Create Date: 2026-08-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_documents_and_entities'
down_revision: Union[str, None] = '003_memory_lifecycle'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'documents',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('source', sa.String(), nullable=False, server_default='upload'),
        sa.Column('file_type', sa.String(), nullable=False),
        sa.Column('original_filename', sa.String(), nullable=True),
        sa.Column('author', sa.String(), nullable=True),
        sa.Column('tags', sa.JSON(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('structured_data', sa.JSON(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_documents_title'), 'documents', ['title'], unique=False)
    op.create_index(op.f('ix_documents_source'), 'documents', ['source'], unique=False)
    op.create_index(op.f('ix_documents_file_type'), 'documents', ['file_type'], unique=False)
    op.create_index(op.f('ix_documents_content_hash'), 'documents', ['content_hash'], unique=False)
    op.create_index(op.f('ix_documents_deleted_at'), 'documents', ['deleted_at'], unique=False)

    op.create_table(
        'entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('entity_type', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('details', sa.JSON(), nullable=False),
        sa.Column('document_id', sa.String(length=36), nullable=False),
        sa.Column('confidence', sa.Integer(), nullable=False, server_default='70'),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_entities_entity_type'), 'entities', ['entity_type'], unique=False)
    op.create_index(op.f('ix_entities_name'), 'entities', ['name'], unique=False)
    op.create_index(op.f('ix_entities_document_id'), 'entities', ['document_id'], unique=False)

    op.create_table(
        'entity_relationships',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('source_entity_id', sa.Integer(), nullable=False),
        sa.Column('target_entity_id', sa.Integer(), nullable=False),
        sa.Column('relationship_type', sa.String(), nullable=False, server_default='co_occurs_in_document'),
        sa.ForeignKeyConstraint(['source_entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_entity_relationships_source_entity_id'), 'entity_relationships', ['source_entity_id'], unique=False)
    op.create_index(op.f('ix_entity_relationships_target_entity_id'), 'entity_relationships', ['target_entity_id'], unique=False)
    op.create_index(op.f('ix_entity_relationships_relationship_type'), 'entity_relationships', ['relationship_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_entity_relationships_relationship_type'), table_name='entity_relationships')
    op.drop_index(op.f('ix_entity_relationships_target_entity_id'), table_name='entity_relationships')
    op.drop_index(op.f('ix_entity_relationships_source_entity_id'), table_name='entity_relationships')
    op.drop_table('entity_relationships')

    op.drop_index(op.f('ix_entities_document_id'), table_name='entities')
    op.drop_index(op.f('ix_entities_name'), table_name='entities')
    op.drop_index(op.f('ix_entities_entity_type'), table_name='entities')
    op.drop_table('entities')

    op.drop_index(op.f('ix_documents_deleted_at'), table_name='documents')
    op.drop_index(op.f('ix_documents_content_hash'), table_name='documents')
    op.drop_index(op.f('ix_documents_file_type'), table_name='documents')
    op.drop_index(op.f('ix_documents_source'), table_name='documents')
    op.drop_index(op.f('ix_documents_title'), table_name='documents')
    op.drop_table('documents')
