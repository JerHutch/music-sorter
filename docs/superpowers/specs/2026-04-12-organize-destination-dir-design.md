# Organize Destination Directory

**Date:** 2026-04-12
**Status:** Approved

## Problem

`RenamePreview._run_dryrun` currently falls back to the first source directory as `base_dir` for `generate_rename_plan`. This is wrong — renamed files should go to a dedicated destination, separate from the scan sources, configured explicitly by the user.

## Goal

Add a single configurable "Organize Destination" directory. When set, it is used as `base_dir` for all rename/organize operations. When unset, the dry-run is blocked with a clear message directing the user to Settings.

## Section 1: Config

Add `organize_directory: Path | None` to `src/core/config.py`:

```python
@property
def organize_directory(self) -> Path | None:
    val = self._data.get("organize_directory")
    return Path(val) if val else None

@organize_directory.setter
def organize_directory(self, path: Path | None) -> None:
    self._data["organize_directory"] = str(path) if path else None
```

Stored in YAML as `organize_directory: /path/to/dir` or absent. Absence means `None` (unset). No default config entry needed.

## Section 2: SettingsView UI

New **"Organize"** group box in `src/gui/settings_view.py`, added after the Source Directories group.

**Controls:**
- `QLabel("Destination:")` + `QLineEdit` (placeholder: "Folder where renamed files are moved…") + `QPushButton("Browse…")`
- Below the path row: a `QLabel` warning, hidden by default, shown in amber (`color: #e67e22`) when the entered path is the same as, a parent of, or a child of any configured source directory

**Behaviour:**
- Overlap warning rechecks on every `textChanged` of the destination field
- `Browse…` opens `QFileDialog.getExistingDirectory`; on selection, sets the field and emits `settings_changed`
- `textChanged` emits `settings_changed`
- `load_config(config)` populates the field from `config.organize_directory`

**New getter:**
```python
def get_organize_directory(self) -> Path | None:
    text = self._organize_path.text().strip()
    return Path(text) if text else None
```

## Section 3: main_window and RenamePreview wiring

**`main_window._save_config`** gains one line:
```python
self._config.organize_directory = self._settings_view.get_organize_directory()
```

**`RenamePreview._run_dryrun`** — replace the current source-directory guard with:
```python
base_dir = self._config.organize_directory if self._config else None
if not base_dir:
    self._status_label.setText("Set an Organize Destination in Settings first.")
    return
```

`load_config` on startup already calls `self._settings_view.load_config(self._config)` — no change needed there.

## Out of Scope

- Per-bucket destination directories
- Blocking save when destination overlaps a source (warning only, not enforced)
- Migrating existing `organize_directory` from source dirs
