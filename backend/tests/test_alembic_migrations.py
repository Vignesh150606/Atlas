import pytest
from alembic.config import Config
from alembic import command

def test_alembic_config_loads():
    alembic_cfg = Config("alembic.ini")
    assert alembic_cfg.get_main_option("script_location") == "alembic"
