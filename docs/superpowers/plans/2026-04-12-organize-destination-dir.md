# Organize Destination Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a configurable "Organize Destination" directory to Settings that is used as the `base_dir` for all rename/organize operations, with the dry-run blocked if it is unset.

**Architecture:** Three-layer change: `Config` gains an `organize_directory` property; `SettingsView` gains an Organize group box with a path field, browse button, and source-overlap warning; `main_window._save_config` and `RenamePreview._run_dryrun` are wired to use it.

**Tech Stack:** Python 3.11+, PySide6, PyYAML, `src.core.config.Config`

---

### Task 1: Add `organize_directory` to `Config`

**Files:**
- Modify: `src/core/config.py`
- Test: `tests/core/test_config.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/core/test_config.py`:

```python
def test_organize_directory_defaults_to_none():
    config = Config({"rename_patterns": {"default": "{title}.mp3"}})
    assert config.organize_directory is None


def test_organize_directory_round_trips(tmp_path):
    config = Config({})
    config.organize_directory = Path("/music/organized")
    out = tmp_path / "config.yaml"
    config.save(out)
    reloaded = Config.load(out)
    assert reloaded.organize_directory == Path("/music/organized")


def test_organize_directory_none_clears_value(tmp_path):
    config = Config({"organize_directory": "/music/organized"})
    config.organize_directory = None
    out = tmp_path / "config.yaml"
    config.save(out)
    reloaded = Config.load(out)
    assert reloaded.organize_directory is None
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest tests/core/test_config.py -v -k "organize_directory"
```

Expected: 3 failures — `AttributeError: 'Config' object has no attribute 'organize_directory'`

- [ ] **Step 3: Add the property and setter to `Config`**

In `src/core/config.py`, add after the `analysis` property (around line 134):

```python
    @property
    def organize_directory(self) -> Path | None:
        val = self._data.get("organize_directory")
        return Path(val) if val else None

    @organize_directory.setter
    def organize_directory(self, path: Path | None) -> None:
        self._data["organize_directory"] = str(path) if path else None
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest tests/core/test_config.py -v -k "organize_directory"
```

Expected: 3 passes.

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest --tb=short -q
```

Expected: all 251 tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/config.py tests/core/test_config.py
git commit -m "feat: add organize_directory to Config"
```

---

### Task 2: Add Organize group box to `SettingsView`

**Files:**
- Modify: `src/gui/settings_view.py`
- Create: `tests/gui/test_settings_view.py`

- [ ] **Step 1: Write failing tests**

Create `tests/gui/test_settings_view.py`:

```python
from pathlib import Path
import pytest
from src.core.config import Config
from src.gui.settings_view import SettingsView


def test_get_organize_directory_returns_none_when_empty(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    assert view.get_organize_directory() is None


def test_get_organize_directory_returns_path_when_set(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._organize_path.setText("/music/organized")
    assert view.get_organize_directory() == Path("/music/organized")


def test_load_config_populates_organize_directory(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    config = Config({"organize_directory": "/music/organized"})
    view.load_config(config)
    assert view.get_organize_directory() == Path("/music/organized")


def test_overlap_warning_hidden_when_path_is_clear(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._dir_list.addItem("/music/source")
    view._organize_path.setText("/music/organized")
    assert not view._overlap_warning.isVisible()


def test_overlap_warning_shown_when_dest_is_under_source(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._dir_list.addItem("/music/source")
    view._organize_path.setText("/music/source/organized")
    assert view._overlap_warning.isVisible()


def test_overlap_warning_shown_when_source_is_under_dest(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._dir_list.addItem("/music/source/sub")
    view._organize_path.setText("/music/source")
    assert view._overlap_warning.isVisible()


def test_overlap_warning_shown_when_dest_equals_source(qtbot):
    view = SettingsView()
    qtbot.addWidget(view)
    view._dir_list.addItem("/music/source")
    view._organize_path.setText("/music/source")
    assert view._overlap_warning.isVisible()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest tests/gui/test_settings_view.py -v
```

Expected: 7 failures — `AttributeError: 'SettingsView' object has no attribute '_organize_path'`

- [ ] **Step 3: Add the Organize group box to `SettingsView.__init__`**

In `src/gui/settings_view.py`, add the Organize group box **after** the iTunes group and **before** the AcoustID group. Find the line `# --- AcoustID ---` and insert before it:

```python
        # --- Organize ---
        organize_group = QGroupBox("Organize")
        organize_layout = QVBoxLayout(organize_group)

        organize_row = QHBoxLayout()
        organize_row.addWidget(QLabel("Destination:"))
        self._organize_path = QLineEdit()
        self._organize_path.setPlaceholderText("Folder where renamed files are moved…")
        btn_browse_org = QPushButton("Browse…")
        organize_row.addWidget(self._organize_path, stretch=1)
        organize_row.addWidget(btn_browse_org)
        organize_layout.addLayout(organize_row)

        self._overlap_warning = QLabel("⚠ Destination overlaps a source directory.")
        self._overlap_warning.setStyleSheet("color: #e67e22;")
        self._overlap_warning.setVisible(False)
        organize_layout.addWidget(self._overlap_warning)

        btn_browse_org.clicked.connect(self._browse_organize_dir)
        self._organize_path.textChanged.connect(self._check_overlap)
        self._organize_path.textChanged.connect(lambda: self.settings_changed.emit())

        layout.addWidget(organize_group)

```

- [ ] **Step 4: Add `_browse_organize_dir`, `_check_overlap`, and `get_organize_directory`**

Append these methods to `SettingsView` (before the final closing of the class):

```python
    def _browse_organize_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Organize Destination")
        if path:
            self._organize_path.setText(path)

    def _check_overlap(self) -> None:
        """Show warning if destination overlaps any source directory."""
        dest_text = self._organize_path.text().strip()
        if not dest_text:
            self._overlap_warning.setVisible(False)
            return
        dest = Path(dest_text)
        for src in self.get_source_directories():
            try:
                dest.relative_to(src)   # dest is under src (or equal)
                self._overlap_warning.setVisible(True)
                return
            except ValueError:
                pass
            try:
                src.relative_to(dest)   # src is under dest
                self._overlap_warning.setVisible(True)
                return
            except ValueError:
                pass
        self._overlap_warning.setVisible(False)

    def get_organize_directory(self) -> Path | None:
        text = self._organize_path.text().strip()
        return Path(text) if text else None
```

- [ ] **Step 5: Update `load_config` to populate the organize path**

In `SettingsView.load_config`, add after the `acoustid_api_key` block:

```python
        if config.organize_directory:
            self._organize_path.setText(str(config.organize_directory))
```

- [ ] **Step 6: Update `_add_directory` and `_remove_directory` to recheck overlap**

In `_add_directory`, add `self._check_overlap()` before the `settings_changed.emit()` call:

```python
    def _add_directory(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Music Directory")
        if path:
            self._dir_list.addItem(path)
            self._check_overlap()
            self.settings_changed.emit()
```

In `_remove_directory`, same:

```python
    def _remove_directory(self) -> None:
        for item in self._dir_list.selectedItems():
            self._dir_list.takeItem(self._dir_list.row(item))
        self._check_overlap()
        self.settings_changed.emit()
```

- [ ] **Step 7: Run the settings view tests**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest tests/gui/test_settings_view.py -v
```

Expected: all 7 pass.

- [ ] **Step 8: Run full suite for regressions**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add src/gui/settings_view.py tests/gui/test_settings_view.py
git commit -m "feat: add Organize Destination field to SettingsView"
```

---

### Task 3: Wire `organize_directory` into `main_window` and `RenamePreview`

**Files:**
- Modify: `src/gui/main_window.py`
- Modify: `src/gui/rename_preview.py`
- Test: `tests/gui/test_rename_preview.py`

- [ ] **Step 1: Write failing test for blocked dry-run**

Append to `tests/gui/test_rename_preview.py`:

```python
def test_dryrun_blocked_when_no_organize_directory(qtbot):
    """Dry-run shows a message and does not proceed when organize_directory is unset."""
    from src.core.config import Config
    view = RenamePreview()
    qtbot.addWidget(view)
    config = Config({"rename_patterns": {"default": "{title}.mp3"}})
    # organize_directory is not set — config.organize_directory is None
    view.set_tracks([_track()])
    view.set_config(config)
    view._run_dryrun()
    assert view._status_label.text() == "Set an Organize Destination in Settings first."
    assert view.operation_count() == 0
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest tests/gui/test_rename_preview.py::test_dryrun_blocked_when_no_organize_directory -v
```

Expected: FAIL — the status label will show a different message (current code checks `source_directories`).

- [ ] **Step 3: Update `RenamePreview._run_dryrun` to use `organize_directory`**

In `src/gui/rename_preview.py`, find the current guard block in `_run_dryrun`:

```python
        if not self._config or not self._config.source_directories:
            self._status_label.setText("No source directory configured — set one in Settings.")
            return
        base_dir = self._config.source_directories[0]
```

Replace with:

```python
        base_dir = self._config.organize_directory if self._config else None
        if not base_dir:
            self._status_label.setText("Set an Organize Destination in Settings first.")
            return
```

- [ ] **Step 4: Run the new test to confirm it passes**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest tests/gui/test_rename_preview.py::test_dryrun_blocked_when_no_organize_directory -v
```

Expected: PASS.

- [ ] **Step 5: Update `main_window._save_config` to persist `organize_directory`**

In `src/gui/main_window.py`, find `_save_config`:

```python
    def _save_config(self) -> None:
        self._config.source_directories = self._settings_view.get_source_directories()
        self._config.itunes_xml_path = self._settings_view.get_itunes_path()
        self._config.acoustid_api_key = self._settings_view.get_acoustid_api_key()
        self._config.save(self._config_path)
```

Replace with:

```python
    def _save_config(self) -> None:
        self._config.source_directories = self._settings_view.get_source_directories()
        self._config.itunes_xml_path = self._settings_view.get_itunes_path()
        self._config.acoustid_api_key = self._settings_view.get_acoustid_api_key()
        self._config.organize_directory = self._settings_view.get_organize_directory()
        self._config.save(self._config_path)
```

- [ ] **Step 6: Run full test suite**

```bash
cd /mnt/cloud/code/music-sorter && uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/gui/rename_preview.py src/gui/main_window.py tests/gui/test_rename_preview.py
git commit -m "feat: wire organize_directory into RenamePreview and main_window"
```

---

### Task 4: Update documentation

**Files:**
- Modify: `docs/guides/rename-organize.md`
- Modify: `docs/guides/getting-started.md`

- [ ] **Step 1: Add a Prerequisites section to `docs/guides/rename-organize.md`**

Insert a new `## Prerequisites` section after the `## How It Works` section and before `## Pattern Syntax`:

```markdown
## Prerequisites

Before running a rename, set an **Organize Destination** directory in Settings:

1. Click **Settings** in the top navigation bar.
2. Under **Organize**, click **Browse…** and select a folder where renamed files will be moved. This must be a directory separate from your source directories.
3. Click anywhere else — the setting saves automatically.

If no Organize Destination is configured, the dry-run preview is blocked with a reminder message.
```

- [ ] **Step 2: Update `docs/guides/getting-started.md` basic workflow**

In the `## Basic Workflow` section, step 5 currently reads:

```markdown
5. When tags are clean, use **Organize → Rename / Organize** to restructure files on disk according to your configured patterns.
```

Replace with:

```markdown
5. Set an **Organize Destination** in Settings (under the Organize section) — this is where renamed files will be moved. Then use **Organize → Rename / Organize** to restructure files on disk according to your configured patterns.
```

- [ ] **Step 3: Commit**

```bash
git add docs/guides/rename-organize.md docs/guides/getting-started.md
git commit -m "docs: document organize destination directory in guides"
```
