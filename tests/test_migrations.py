"""The Alembic migration chain builds the full schema from scratch."""

from __future__ import annotations

import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from sr.models import Base


def test_upgrade_head_creates_every_model_table(tmp_path):
    db_url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)

    command.upgrade(cfg, "head")

    insp = sa.inspect(sa.create_engine(db_url))
    tables = set(insp.get_table_names())
    for model_table in Base.metadata.tables:
        assert model_table in tables, f"{model_table} missing after upgrade head"
