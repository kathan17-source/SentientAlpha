"""Read the database URL from environment, never from committed credentials."""

from alembic import context
from sentientalpha.config import Settings
from sentientalpha.database.models import Base
from sentientalpha.database.session import make_engine

settings = Settings.from_env()
if context.is_offline_mode():
    context.configure(
        url=settings.database_url,
        target_metadata=Base.metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = make_engine(settings.database_url)
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection, target_metadata=Base.metadata, compare_type=True
            )
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()
