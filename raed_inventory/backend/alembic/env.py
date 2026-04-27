"""
Alembic environment script for Raed Inventory System.

Key design decisions
--------------------
1. DATABASE_URL is always read from ``app.config.settings`` — never from
   alembic.ini.  This means the ENV_FILE environment variable (defaulting to
   ".env") controls which credential file is loaded, exactly as the
   application itself does.

2. All SQLAlchemy models are imported through ``app.models`` so that
   ``target_metadata`` is always in sync with the codebase.

3. Both **offline** (generate SQL script) and **online** (run against a live
   DB) modes are supported.

4. SQLite is supported for local development; PostgreSQL is used for staging
   and production.

Usage examples
--------------
# Generate a new migration (auto-detect changes):
    alembic revision --autogenerate -m "describe the change"

# Apply pending migrations:
    alembic upgrade head

# Downgrade one step:
    alembic downgrade -1

# Show current revision:
    alembic current

# Show migration history:
    alembic history --verbose
"""

from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

# ---------------------------------------------------------------------------
# Alembic Config object — gives access to values in alembic.ini
# ---------------------------------------------------------------------------
config = context.config

# Set up Python logging from the [loggers] section in alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ---------------------------------------------------------------------------
# Import application models so autogenerate can detect schema changes
# ---------------------------------------------------------------------------
# Import Base first, then all model classes so their tables are registered.
from app.database import Base  # noqa: E402
import app.models  # noqa: E402, F401  — side-effect: registers all ORM models

target_metadata = Base.metadata

# ---------------------------------------------------------------------------
# Inject the live DATABASE_URL from app config into Alembic config
# ---------------------------------------------------------------------------
from app.config import settings as _settings  # noqa: E402

# Override whatever (empty) sqlalchemy.url alembic.ini has
config.set_main_option("sqlalchemy.url", _settings.DATABASE_URL)


# ---------------------------------------------------------------------------
# Offline migration (--sql flag / no live DB connection)
# ---------------------------------------------------------------------------

def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.

    This configures the context with just a URL and not an Engine; calls to
    context.execute() emit the SQL to the script output.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Emit BEGIN/COMMIT so the output is ready-to-run SQL
        include_schemas=False,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online migration (live DB connection)
# ---------------------------------------------------------------------------

def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.

    Creates an Engine, obtains a connection, and runs migrations inside a
    transaction.  SQLite requires ``check_same_thread=False``; PostgreSQL
    uses the default pool.
    """
    url = config.get_main_option("sqlalchemy.url")

    # SQLite: disable connection pool for alembic (avoids thread issues)
    is_sqlite = url.startswith("sqlite")
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    poolclass = pool.StaticPool if is_sqlite else pool.NullPool

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=poolclass,
        connect_args=connect_args,
        url=url,
    )

    with connectable.connect() as connection:
        if is_sqlite:
            # Local recovery mode: if the disk previously filled up, SQLite
            # journaling can become wedged and metadata introspection may fail
            # with "disk I/O error". Disable journaling for this maintenance
            # connection only.
            connection.exec_driver_sql("PRAGMA journal_mode=OFF")
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,           # detect column type changes
            compare_server_default=True, # detect server default changes
        )

        with context.begin_transaction():
            context.run_migrations()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
