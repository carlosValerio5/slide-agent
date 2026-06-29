import tempfile
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "sample.md"


@pytest.fixture
def sample_text() -> str:
    return FIXTURE.read_text(encoding="utf-8")


@pytest.fixture
def tmp_store():
    from services.pipeline.graph.store import GraphStore

    path = tempfile.mkdtemp()
    store = GraphStore(path)
    yield store
    store.close()
