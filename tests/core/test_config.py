from pathlib import Path

import pytest

from src.core.config import Config


def test_load_default_config():
    config = Config.load_defaults()
    assert config.required_tags["global"] == [
        "title", "artist", "album", "genre", "year", "bucket"
    ]
    assert config.deduplication["similarity_threshold"] == 0.85


def test_load_from_file(tmp_path):
    user_config = tmp_path / "config.yaml"
    user_config.write_text(
        "source_directories:\n"
        "  - /home/user/music\n"
        "deduplication:\n"
        "  similarity_threshold: 0.90\n"
    )
    config = Config.load(user_config)
    assert config.source_directories == [Path("/home/user/music")]
    assert config.deduplication["similarity_threshold"] == 0.90
    # Defaults still present for unset keys
    assert config.required_tags["global"] == [
        "title", "artist", "album", "genre", "year", "bucket"
    ]


def test_save_config(tmp_path):
    config = Config.load_defaults()
    config.source_directories = [Path("/music/collection")]
    out = tmp_path / "saved.yaml"
    config.save(out)
    reloaded = Config.load(out)
    assert reloaded.source_directories == [Path("/music/collection")]


def test_get_required_tags_for_bucket():
    config = Config.load_defaults()
    dj_tags = config.get_required_tags("DJ Music")
    assert "bpm" in dj_tags
    assert "key" in dj_tags
    assert "title" in dj_tags  # global tags included

    general_tags = config.get_required_tags("General")
    assert "bpm" not in general_tags
    assert "title" in general_tags


def test_get_rename_pattern():
    config = Config.load_defaults()
    assert "{bpm}" in config.get_rename_pattern("DJ Music")
    assert config.get_rename_pattern("Unknown Bucket") == config.rename_patterns["default"]
