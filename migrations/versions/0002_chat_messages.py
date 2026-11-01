"""chat messages

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('chat_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=True),
        sa.Column('role', sa.String(length=12), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('meta', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'))
    with op.batch_alter_table('chat_messages', schema=None) as b:
        b.create_index(b.f('ix_chat_messages_user_id'), ['user_id'], unique=False)
        b.create_index(b.f('ix_chat_messages_incident_id'), ['incident_id'], unique=False)
        b.create_index(b.f('ix_chat_messages_created_at'), ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_table('chat_messages')
