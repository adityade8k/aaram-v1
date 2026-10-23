"""Pytest configuration for path setup."""

import os
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).parents[1].resolve()
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


# Make tests reproducible by ignoring machine-specific profile/tool env config.
# Without this, importing config during test collection can pick up a developer's
# local .env and fail before tests run.
os.environ["REACHY_MINI_SKIP_DOTENV"] = "1"
os.environ.pop("REACHY_MINI_CUSTOM_PROFILE", None)
os.environ.pop("REACHY_MINI_EXTERNAL_PROFILES_DIRECTORY", None)
os.environ.pop("REACHY_MINI_EXTERNAL_TOOLS_DIRECTORY", None)
os.environ.pop("REACHY_MINI_GROUNDING_FILE", None)
os.environ.pop("REACHY_MINI_REASONING_ENABLED", None)
os.environ.pop("REACHY_MINI_REASONING_MODEL", None)
os.environ.pop("REACHY_MINI_REASONING_GROUNDING_FILE", None)
os.environ.pop("REACHY_MINI_REASONING_EFFORT", None)

os.environ.pop("REACHY_MINI_REASONING_WEB_SEARCH", None)


@pytest.fixture(autouse=True)
def isolate_experiment_storage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep automatic experiment recording outside the user's real app data."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
