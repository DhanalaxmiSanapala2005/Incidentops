"""alert external id and RAG chunk vectors

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('alerts', schema=None) as b:
        b.add_column(sa.Column('external_id', sa.String(length=80), nullable=True))
        b.create_index(b.f('ix_alerts_external_id'), ['external_id'], unique=False)
    op.create_table('chunk_vectors',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('chunk_id', sa.String(length=220), nullable=False),
        sa.Column('model', sa.String(length=80), nullable=False),
        sa.Column('text_hash', sa.String(length=40), nullable=False),
        sa.Column('vector', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('chunk_vectors', schema=None) as b:
        b.create_index(b.f('ix_chunk_vectors_chunk_id'), ['chunk_id'], unique=False)


def downgrade() -> None:
    op.drop_table('chunk_vectors')
    with op.batch_alter_table('alerts', schema=None) as b:
        b.drop_index(b.f('ix_alerts_external_id')); b.drop_column('external_id')
