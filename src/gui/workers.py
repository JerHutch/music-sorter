import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from src.core.artwork import embed_artwork, find_local_artwork, search_cover_art
import src.core.artwork as _artwork_mod
from src.core.analyzer import detect_bpm, detect_key
from src.core.database import Database
from src.core.deduplicator import find_duplicates
from src.core.fingerprint import generate_fingerprint, lookup_metadata
from src.core.itunes import match_itunes_to_files, parse_itunes_xml, resolve_conflicts as _resolve_conflicts
from src.core.models import DupeGroup, RenameOperation, TagConflict, Track
from src.core.organizer import execute_rename_plan
from src.core.scanner import scan_directories
from src.core.tagger import COMPLETENESS_FIELDS, read_tags, write_tags

logger = logging.getLogger(__name__)


# Public alias used by tests
def resolve_itunes_conflicts(track, itunes_entry):
    return _resolve_conflicts(track, itunes_entry)


def upsert_track_in_db(db: Database, track: Track, file_mtime: float) -> None:
    db.upsert_track(track, file_mtime=file_mtime)


class ScanWorker(QThread):
    progress = Signal(int, str)
    finished = Signal(int)

    def __init__(self, directories, db):
        super().__init__()
        self._directories = directories
        self._db = db
        self._cancelled = False

    def run(self):
        logger.info("Scan started across %d directories", len(self._directories))
        paths = scan_directories(self._directories, on_progress=self._on_scan_progress)
        for i, path in enumerate(paths):
            if self._cancelled:
                logger.info("Scan cancelled after %d files", i)
                break
            try:
                track = read_tags(path)
                mtime = path.stat().st_mtime
                self._db.upsert_track(track, file_mtime=mtime)
            except Exception:
                logger.exception("Failed to process file: %s", path)
            self.progress.emit(i + 1, str(path))
        logger.info("Scan finished: processed %d files", len(paths))
        self.finished.emit(len(paths))

    def _on_scan_progress(self, count, current_dir):
        self.progress.emit(count, current_dir)

    def cancel(self):
        self._cancelled = True


class DedupeWorker(QThread):
    """Runs find_duplicates in a background thread."""

    progress = Signal(int, int)   # processed, total
    finished = Signal(list)       # list[DupeGroup]
    error = Signal(str)

    def __init__(self, tracks: list[Track], duration_tolerance: float = 2.0,
                 similarity_threshold: float = 0.85):
        super().__init__()
        self._tracks = tracks
        self._duration_tolerance = duration_tolerance
        self._similarity_threshold = similarity_threshold

    def run(self):
        logger.info("DedupeWorker: scanning %d tracks for duplicates", len(self._tracks))
        try:
            groups = find_duplicates(
                self._tracks,
                duration_tolerance=self._duration_tolerance,
                similarity_threshold=self._similarity_threshold,
                on_progress=lambda cur, total: self.progress.emit(cur, total),
            )
            logger.info("DedupeWorker: found %d duplicate groups", len(groups))
            self.finished.emit(groups)
        except Exception as exc:
            logger.exception("DedupeWorker failed")
            self.error.emit(str(exc))
            self.finished.emit([])


class TagWriteWorker(QThread):
    """Writes tags for one or more tracks in a background thread."""

    progress = Signal(int, int)   # completed, total
    finished = Signal(list)       # list[Track] — updated tracks
    error = Signal(str)

    def __init__(self, track_field_pairs: list[tuple[Track, list[str]]], db: Database):
        super().__init__()
        self._pairs = track_field_pairs
        self._db = db

    def run(self):
        updated: list[Track] = []
        total = len(self._pairs)
        for i, (track, fields) in enumerate(self._pairs, 1):
            try:
                write_tags(track.file_path, track, fields)
                track.tag_completeness = track.compute_completeness(COMPLETENESS_FIELDS)
                try:
                    mtime = track.file_path.stat().st_mtime
                except OSError:
                    logger.warning("TagWriteWorker: could not stat %s, using mtime=0.0", track.file_path)
                    mtime = 0.0
                upsert_track_in_db(self._db, track, file_mtime=mtime)
                updated.append(track)
            except Exception:
                logger.exception("TagWriteWorker: failed to write %s", track.file_path)
            self.progress.emit(i, total)
        self.finished.emit(updated)


class ITunesWorker(QThread):
    """Parses iTunes XML and matches/conflicts against the local library."""

    progress = Signal(str)         # status message
    finished = Signal(list)        # list[TagConflict]
    error = Signal(str)

    def __init__(self, xml_path: Path, tracks: list[Track], source_directories: list[Path]):
        super().__init__()
        self._xml_path = xml_path
        self._tracks = tracks
        self._source_dirs = source_directories

    def run(self):
        try:
            self.progress.emit("Parsing iTunes XML…")
            entries = parse_itunes_xml(self._xml_path)
            self.progress.emit(f"Matching {len(entries)} iTunes entries to library…")
            matched, _unmatched = match_itunes_to_files(entries, self._tracks, self._source_dirs)
            conflicts: list[TagConflict] = []
            for itunes_entry, track in matched:
                conflicts.extend(resolve_itunes_conflicts(track, itunes_entry))
            self.progress.emit(f"Found {len(conflicts)} conflicts.")
            self.finished.emit(conflicts)
        except Exception as exc:
            logger.exception("ITunesWorker failed")
            self.error.emit(str(exc))
            self.finished.emit([])


class RenameWorker(QThread):
    """Executes a rename plan in a background thread."""

    progress = Signal(int, int)    # completed, total
    finished = Signal(list)        # list[RenameOperation] — executed ops
    error = Signal(str)

    def __init__(self, plan: list[RenameOperation], dry_run: bool = False):
        super().__init__()
        self._plan = plan
        self._dry_run = dry_run

    def run(self):
        try:
            result = execute_rename_plan(
                self._plan,
                dry_run=self._dry_run,
                on_progress=lambda cur, total: self.progress.emit(cur, total),
            )
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("RenameWorker failed")
            self.error.emit(str(exc))
            self.finished.emit([])


class AnalyzeWorker(QThread):
    """Detects BPM and key for a list of tracks, writes the results back to disk and DB."""

    progress = Signal(int, int)   # completed, total
    finished = Signal(list)       # list[Track] — updated tracks
    error = Signal(str)

    def __init__(self, tracks: list[Track], db: Database):
        super().__init__()
        self._tracks = tracks
        self._db = db
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self):
        total = len(self._tracks)
        updated: list[Track] = []
        for i, track in enumerate(self._tracks, 1):
            if self._cancelled:
                break
            try:
                bpm = detect_bpm(track.file_path)
                key = detect_key(track.file_path)
                changed: list[str] = []
                if bpm is not None:
                    track.bpm = bpm
                    changed.append("bpm")
                if key is not None:
                    track.key = key
                    changed.append("key")
                if changed:
                    write_tags(track.file_path, track, changed)
                    track.tag_completeness = track.compute_completeness(COMPLETENESS_FIELDS)
                    try:
                        mtime = track.file_path.stat().st_mtime
                    except OSError:
                        mtime = 0.0
                    upsert_track_in_db(self._db, track, file_mtime=mtime)
                    updated.append(track)
            except Exception:
                logger.exception("AnalyzeWorker: failed on %s", track.file_path)
            self.progress.emit(i, total)
        self.finished.emit(updated)


_AUTOTAG_FIELDS = ["title", "artist", "album", "album_artist", "track_number", "year"]


class AutoTagWorker(QThread):
    """Fingerprints tracks, looks up metadata via AcoustID + MusicBrainz, and builds
    a list of TagConflict objects for fields that differ from existing tag values.
    """

    progress = Signal(int, int)   # completed, total
    finished = Signal(list, int)  # list[TagConflict], unmatched_count
    error = Signal(str)

    def __init__(self, tracks: list[Track], db: Database, api_key: str = ""):
        super().__init__()
        self._tracks = tracks
        self._db = db
        self._api_key = api_key
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = len(self._tracks)
        conflicts: list[TagConflict] = []
        unmatched = 0
        try:
            for i, track in enumerate(self._tracks, 1):
                if self._cancelled:
                    break
                try:
                    fp_result = generate_fingerprint(track.file_path)
                    if fp_result is None:
                        unmatched += 1
                        track.acoustid_no_match = True
                        self._upsert(track)
                        self.progress.emit(i, total)
                        continue

                    fp, fp_duration = fp_result
                    track.fingerprint = fp
                    meta = lookup_metadata(fp, fp_duration, api_key=self._api_key)
                    if meta is None:
                        unmatched += 1
                        track.acoustid_no_match = True
                        self._upsert(track)
                        self.progress.emit(i, total)
                        continue

                    track.acoustid_no_match = False
                    self._upsert(track)

                    for field in _AUTOTAG_FIELDS:
                        found_val = meta.get(field)
                        if found_val is None:
                            continue
                        current_val = getattr(track, field, None)
                        found_str = str(found_val)
                        current_str = str(current_val) if current_val is not None else ""
                        if found_str != current_str:
                            conflicts.append(TagConflict(
                                file_path=track.file_path,
                                field=field,
                                local_value=current_str,
                                incoming_value=found_str,
                            ))
                except Exception:
                    logger.exception("AutoTagWorker: failed on %s", track.file_path)
                self.progress.emit(i, total)
        except Exception as exc:
            self.error.emit(str(exc))
            return
        self.finished.emit(conflicts, unmatched)

    def _upsert(self, track: Track) -> None:
        try:
            mtime = track.file_path.stat().st_mtime
        except OSError:
            mtime = 0.0
        upsert_track_in_db(self._db, track, file_mtime=mtime)


class ArtworkWorker(QThread):
    """Scans for artwork (local folder → MusicBrainz) and embeds it immediately.

    Processes tracks sequentially to respect MusicBrainz rate limits.
    Emits finished(track, success, image_data) once per track and done() when all complete.
    """

    finished = Signal(object, bool, bytes)  # track, success, image_data (b"" on failure)
    done = Signal()                         # fires once when all tracks are processed
    status_message = Signal(str)            # for the main window status bar
    progress = Signal(int, int)             # completed, total

    def __init__(self, tracks: list[Track]):
        super().__init__()
        self._tracks = tracks
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        total = len(self._tracks)
        for i, track in enumerate(self._tracks, 1):
            if self._cancelled:
                break
            try:
                data = find_local_artwork(track.file_path)
                if data:
                    embed_artwork(track.file_path, data)
                    self.finished.emit(track, True, data)
                elif _artwork_mod.musicbrainzngs is None:
                    self.status_message.emit("MusicBrainz unavailable — artwork not found")
                    self.finished.emit(track, False, b"")
                else:
                    data = search_cover_art(track.artist or "", track.album or "")
                    if data:
                        embed_artwork(track.file_path, data)
                        self.finished.emit(track, True, data)
                    else:
                        self.status_message.emit(
                            f"No artwork found for {track.artist} — {track.album}"
                        )
                        self.finished.emit(track, False, b"")
            except Exception:
                logger.exception("ArtworkWorker: failed for %s", track.file_path)
                self.finished.emit(track, False, b"")
            self.progress.emit(i, total)
        self.done.emit()
