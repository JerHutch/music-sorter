from __future__ import annotations

import copy
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_DEFAULTS_PATH = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"
USER_CONFIG_PATH = Path.home() / ".config" / "music-sorter" / "config.yaml"


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base, returning a new dict."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


class Config:
    """Application configuration backed by YAML files."""

    def __init__(self, data: dict):
        self._data = data

    @classmethod
    def load_user_config(cls, path: Path = USER_CONFIG_PATH) -> "Config":
        """Load config from user path, creating it from defaults if absent."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.error("Failed to create config directory: %s", path.parent, exc_info=True)

        if not path.exists():
            config = cls.load_defaults()
            try:
                config.save(path)
            except OSError:
                logger.error("Failed to save default config to: %s", path, exc_info=True)
            return config

        try:
            return cls.load(path)
        except Exception:
            logger.error("Failed to load config from: %s", path, exc_info=True)
            return cls.load_defaults()

    @classmethod
    def load_defaults(cls) -> Config:
        with open(_DEFAULTS_PATH) as f:
            data = yaml.safe_load(f)
        return cls(data)

    @classmethod
    def load(cls, path: Path) -> Config:
        with open(_DEFAULTS_PATH) as f:
            defaults = yaml.safe_load(f)
        with open(path) as f:
            overrides = yaml.safe_load(f) or {}
        merged = _deep_merge(defaults, overrides)
        return cls(merged)

    @classmethod
    def load_user_config(cls, path: Path = USER_CONFIG_PATH) -> "Config":
        """Load config from user path, creating it from defaults if absent."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError:
            logger.error("Failed to create config directory: %s", path.parent, exc_info=True)

        if not path.exists():
            config = cls.load_defaults()
            try:
                config.save(path)
            except OSError:
                logger.error("Failed to save default config to: %s", path, exc_info=True)
            return config

        try:
            return cls.load(path)
        except Exception:
            logger.error("Failed to load config from: %s", path, exc_info=True)
            return cls.load_defaults()

    def save(self, path: Path) -> None:
        try:
            with open(path, "w") as f:
                yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)
        except OSError:
            logger.error("Failed to save config to: %s", path, exc_info=True)

    @property
    def source_directories(self) -> list[Path]:
        return [Path(d) for d in self._data.get("source_directories", [])]

    @source_directories.setter
    def source_directories(self, dirs: list[Path]) -> None:
        self._data["source_directories"] = [str(d) for d in dirs]

    @property
    def itunes_xml_path(self) -> Path | None:
        val = self._data.get("itunes_xml_path")
        return Path(val) if val else None

    @itunes_xml_path.setter
    def itunes_xml_path(self, path: Path | None) -> None:
        self._data["itunes_xml_path"] = str(path) if path else None

    @property
    def acoustid_api_key(self) -> str:
        return self._data.get("acoustid_api_key", "")

    @acoustid_api_key.setter
    def acoustid_api_key(self, key: str) -> None:
        self._data["acoustid_api_key"] = key

    @property
    def required_tags(self) -> dict:
        return self._data.get("required_tags", {})

    @property
    def rename_patterns(self) -> dict:
        return self._data.get("rename_patterns", {})

    @property
    def analysis(self) -> dict:
        return self._data.get("analysis", {})

    @property
    def normalization(self) -> dict:
        return self._data.get("normalization", {})

    @property
    def deduplication(self) -> dict:
        return self._data.get("deduplication", {})

    @property
    def library_columns(self) -> dict:
        return self._data.get("library_columns", {})

    @property
    def logging(self) -> dict:
        return self._data.get("logging", {})

    def get_required_tags(self, bucket: str) -> list[str]:
        """Return the full list of required tags for a bucket (global + per-bucket)."""
        tags = list(self.required_tags.get("global", []))
        per_bucket = self.required_tags.get("per_bucket", {})
        if bucket in per_bucket:
            for tag in per_bucket[bucket]:
                if tag not in tags:
                    tags.append(tag)
        return tags

    def set_visible_columns(self, columns: list[str]) -> None:
        if "library_columns" not in self._data:
            self._data["library_columns"] = {}
        self._data["library_columns"]["visible"] = columns

    def get_rename_pattern(self, bucket: str) -> str:
        """Return the rename pattern for a bucket, falling back to default."""
        return self.rename_patterns.get(bucket, self.rename_patterns.get("default", ""))
