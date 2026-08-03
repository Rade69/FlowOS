# ruff: noqa: E402, I001
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
import sys
from pathlib import Path

_src = Path(__file__).resolve().parent.parent / "src"
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from flowos.service.services.infrastructure.persistence.base import Base  # noqa: E402
from flowos.service.services.infrastructure.persistence.engine import (  # noqa: E402
    get_data_directory,
)

# Osiguraj da su svi modeli importovani pre autogenerate
import flowos.service.services.infrastructure.persistence.activity_models  # noqa: E402, F401
import flowos.service.services.infrastructure.persistence.conflict_models  # noqa: E402, F401
import flowos.service.services.infrastructure.persistence.models  # noqa: E402, F401
import flowos.service.services.infrastructure.persistence.plan_models  # noqa: E402, F401
import flowos.service.services.infrastructure.persistence.report_models  # noqa: E402, F401
import flowos.service.services.infrastructure.persistence.resume_models  # noqa: E402, F401
import flowos.service.services.infrastructure.persistence.worktree_models  # noqa: E402, F401

target_metadata = Base.metadata

# Postavi SQLite URL programski — ${LOCALAPPDATA} nije dostupan u ini fajlu
# -x parametar (npr. round-trip test) ima prednost
import sys as _sys

_x_url = None
for _i, _arg in enumerate(_sys.argv):
    if _arg == "-x" and _i + 1 < len(_sys.argv):
        _pair = _sys.argv[_i + 1]
        if "=" in _pair:
            _k, _v = _pair.split("=", 1)
            if _k == "sqlalchemy.url":
                _x_url = _v
                break
if _x_url:
    config.set_main_option("sqlalchemy.url", _x_url)
elif not config.get_main_option("sqlalchemy.url"):
    db_path = get_data_directory() / "flowos.db"
    config.set_main_option(
        "sqlalchemy.url", f"sqlite:///{db_path}"
    )

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
