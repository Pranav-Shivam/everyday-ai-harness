from pathlib import Path

import pytest

from everyday_harness.store import Store


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return Store(tmp_path / "test.sqlite3")
