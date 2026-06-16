from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_salon_context() -> dict:
    return json.loads((FIXTURES / "salon_context.json").read_text(encoding="utf-8"))


@pytest.fixture
def sample_lawyer_context() -> dict:
    return json.loads((FIXTURES / "lawyer_context.json").read_text(encoding="utf-8"))


@pytest.fixture
def tmp_output_dir(tmp_path: Path) -> Path:
    output = tmp_path / "output" / "test_user"
    output.mkdir(parents=True)
    return output
