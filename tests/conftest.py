import shutil
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def tagged_full_mp3(tmp_path) -> Path:
    """A fully tagged MP3 file (copy to tmp so tests don't modify fixtures)."""
    src = FIXTURES_DIR / "tagged_full.mp3"
    dst = tmp_path / "tagged_full.mp3"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def tagged_partial_mp3(tmp_path) -> Path:
    """A partially tagged MP3 file."""
    src = FIXTURES_DIR / "tagged_partial.mp3"
    dst = tmp_path / "tagged_partial.mp3"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def untagged_mp3(tmp_path) -> Path:
    """An MP3 file with no tags."""
    src = FIXTURES_DIR / "untagged.mp3"
    dst = tmp_path / "tagged_untagged.mp3"
    shutil.copy2(src, dst)
    return dst


@pytest.fixture
def music_dir_with_files(tmp_path) -> Path:
    """A directory tree with MP3 files for scanner tests."""
    root = tmp_path / "music"
    electronic = root / "Electronic" / "New Order"
    house = root / "House" / "Deadmau5"
    empty = root / "Empty"

    electronic.mkdir(parents=True)
    house.mkdir(parents=True)
    empty.mkdir(parents=True)

    shutil.copy2(FIXTURES_DIR / "tagged_full.mp3", electronic / "blue_monday.mp3")
    shutil.copy2(FIXTURES_DIR / "tagged_partial.mp3", house / "strobe.mp3")
    shutil.copy2(FIXTURES_DIR / "untagged.mp3", root / "unknown.mp3")

    # Non-MP3 file (should be ignored by scanner)
    (root / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0")

    return root
