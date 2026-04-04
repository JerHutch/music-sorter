from __future__ import annotations

import copy
from pathlib import Path

import yaml


_DEFAULTS_PATH = Path(__file__).parent.parent.parent / "config" / "default_config.yaml"


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

    def save(self, path: Path) -> None:
        with open(path, "w") as f:
            yaml.dump(self._data, f, default_flow_style=False, sort_keys=False)

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

    def get_required_tags(self, bucket: str) -> list[str]:
        """Return the full list of required tags for a bucket (global + per-bucket)."""
        tags = list(self.required_tags.get("global", []))
        per_bucket = self.required_tags.get("per_bucket", {})
        if bucket in per_bucket:
            for tag in per_bucket[bucket]:
                if tag not in tags:
                    tags.append(tag)
        return tags

    def get_rename_pattern(self, bucket: str) -> str:
        """Return the rename pattern for a bucket, falling back to default."""
        return self.rename_patterns.get(bucket, self.rename_patterns.get("default", ""))
