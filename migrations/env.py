from alembic import context
from sqlalchemy import create_engine
from backend.config import settings
from backend.db import Base
import backend.models  # noqa: F401

target_metadata = Base.metadata


def run_migrations_online():
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=conn.dialect.name == "sqlite")
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
