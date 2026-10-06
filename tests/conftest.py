from pathlib import Path
from uuid import uuid4

import pytest

from hx.adapters import FakeAdapter
from hx.config import load_task
from hx.demo import initialize
from hx.engine import Engine
from hx.models import Settings
from hx.store import Store


def pytest_configure(config):
    # Keep fixtures inside this project, including under restricted Windows sessions.
    if not config.option.basetemp:
        fixture_root = Path(__file__).resolve().parents[1] / ".hx"
        fixture_root.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(fixture_root / ("test-" + uuid4().hex[:8]))


@pytest.fixture
def project(tmp_path: Path):
    tasks = initialize(tmp_path / "demo")
    return {path.stem: load_task(path) for path in tasks}


@pytest.fixture
def setup_engine(tmp_path):
    def factory(scenario="success", **overrides):
        settings = Settings(adapter="fake", max_attempts=1, max_revisions=0, **overrides)
        adapter = FakeAdapter(scenario)
        store = Store(tmp_path / "state")
        return Engine(store, settings, adapter), adapter

    return factory
