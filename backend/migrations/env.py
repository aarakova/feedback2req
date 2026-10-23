from alembic import context
from sqlalchemy import create_engine, pool, text

from feedback2req.config import Settings
from feedback2req.persistence.models import Base

config = context.config
url = config.attributes.get("database_url") or Settings().database_url

if context.is_offline_mode():
    context.configure(url=url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
    # All online Alembic invocations, including the standalone CLI, share this
    # transaction-scoped database lock. The same connection executes all DDL and
    # commits the version table before releasing the lock; failures roll it back.
    with engine.begin() as connection:
        connection.execute(text("SELECT pg_advisory_xact_lock(19758515832833874)"))
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()
