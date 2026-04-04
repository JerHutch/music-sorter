from pathlib import Path

import pytest


@pytest.fixture
def tmp_music_dir(tmp_path):
    """Create a temporary directory structure for testing."""
    return tmp_path / "music"


@pytest.fixture
def fixtures_dir():
    """Path to test fixture files."""
    return Path(__file__).parent / "tests" / "fixtures"
