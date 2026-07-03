import logging
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect

from app.db.session import engine

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parents[2]

# The revision representing the schema as it existed before Alembic was
# introduced. Databases created back then have all the tables but no
# alembic_version — they must be stamped here, not re-created.
BASELINE_REVISION = "0001"


def _alembic_config() -> Config:
    cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    return cfg


def run_migrations() -> None:
    cfg = _alembic_config()

    with engine.connect() as connection:
        inspector = inspect(connection)
        has_schema = inspector.has_table("users")
        has_version = inspector.has_table("alembic_version")

    if has_schema and not has_version:
        logger.info(
            "Existing pre-Alembic schema detected; stamping baseline revision %s",
            BASELINE_REVISION,
        )
        command.stamp(cfg, BASELINE_REVISION)

    command.upgrade(cfg, "head")
