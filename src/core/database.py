"""SQLite cache layer for track metadata with FTS5 search support."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from src.core.models import Track

import logging
logger = logging.getLogger(__name__)


_CREATE_TRACKS = """
CREATE TABLE IF NOT EXISTS tracks (
    file_path      TEXT PRIMARY KEY,
    file_size      INTEGER NOT NULL,
    bitrate        INTEGER NOT NULL,
    duration       REAL NOT NULL,
    title          TEXT,
    artist         TEXT,
    album_artist   TEXT,
    album          TEXT,
    track_number   INTEGER,
    disc_number    INTEGER,
    year           INTEGER,
    genre          TEXT,
    bpm            REAL,
    key_           TEXT,
    bucket         TEXT,
    fingerprint    TEXT,
    tag_completeness REAL NOT NULL DEFAULT 0.0,
    tag_source     TEXT,
    has_artwork    INTEGER NOT NULL DEFAULT 0,
    file_mtime     REAL NOT NULL DEFAULT 0.0
)
"""

_CREATE_FTS = """
CREATE VIRTUAL TABLE IF NOT EXISTS tracks_fts USING fts5(
    file_path UNINDEXED,
    title,
    artist,
    album,
    album_artist,
    genre,
    bucket
)
"""

_CREATE_HISTORY = """
CREATE TABLE IF NOT EXISTS history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    action      TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    field       TEXT,
    old_value   TEXT,
    new_value   TEXT,
    session_id  TEXT,
    timestamp   TEXT NOT NULL,
    metadata    TEXT
)
"""

_CREATE_PLAYLISTS = """
CREATE TABLE IF NOT EXISTS playlists (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL UNIQUE,
    filters TEXT NOT NULL,
    folder  TEXT,
    format  TEXT NOT NULL DEFAULT 'm3u',
    sort_by TEXT
)
"""


def _row_to_track(row: sqlite3.Row) -> Track:
    return Track(
        file_path=Path(row["file_path"]),
        file_size=row["file_size"],
        bitrate=row["bitrate"],
        duration=row["duration"],
        title=row["title"],
        artist=row["artist"],
        album_artist=row["album_artist"],
        album=row["album"],
        track_number=row["track_number"],
        disc_number=row["disc_number"],
        year=row["year"],
        genre=row["genre"],
        bpm=row["bpm"],
        key=row["key_"],
        bucket=row["bucket"],
        fingerprint=row["fingerprint"],
        tag_completeness=row["tag_completeness"],
        tag_source=row["tag_source"],
        has_artwork=bool(row["has_artwork"]),
    )


class Database:
    """SQLite-backed cache for track metadata."""

    def __init__(self, db_path: Path) -> None:
        self._path = db_path
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._setup_schema()

    def _setup_schema(self) -> None:
        cur = self._conn
        cur.execute(_CREATE_TRACKS)
        cur.execute(_CREATE_HISTORY)
        cur.execute(_CREATE_PLAYLISTS)
        self._fts_available = False
        try:
            cur.execute(_CREATE_FTS)
            self._fts_available = True
        except sqlite3.OperationalError:
            pass
        self._conn.commit()

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def upsert_track(self, track: Track, file_mtime: float) -> None:
        logger.debug("Upserting track: %s", track.file_path)
        sql = """
        INSERT INTO tracks (
            file_path, file_size, bitrate, duration,
            title, artist, album_artist, album,
            track_number, disc_number, year, genre,
            bpm, key_, bucket, fingerprint,
            tag_completeness, tag_source, has_artwork, file_mtime
        ) VALUES (
            :file_path, :file_size, :bitrate, :duration,
            :title, :artist, :album_artist, :album,
            :track_number, :disc_number, :year, :genre,
            :bpm, :key_, :bucket, :fingerprint,
            :tag_completeness, :tag_source, :has_artwork, :file_mtime
        )
        ON CONFLICT(file_path) DO UPDATE SET
            file_size        = excluded.file_size,
            bitrate          = excluded.bitrate,
            duration         = excluded.duration,
            title            = excluded.title,
            artist           = excluded.artist,
            album_artist     = excluded.album_artist,
            album            = excluded.album,
            track_number     = excluded.track_number,
            disc_number      = excluded.disc_number,
            year             = excluded.year,
            genre            = excluded.genre,
            bpm              = excluded.bpm,
            key_             = excluded.key_,
            bucket           = excluded.bucket,
            fingerprint      = excluded.fingerprint,
            tag_completeness = excluded.tag_completeness,
            tag_source       = excluded.tag_source,
            has_artwork      = excluded.has_artwork,
            file_mtime       = excluded.file_mtime
        """
        params = {
            "file_path": str(track.file_path),
            "file_size": track.file_size,
            "bitrate": track.bitrate,
            "duration": track.duration,
            "title": track.title,
            "artist": track.artist,
            "album_artist": track.album_artist,
            "album": track.album,
            "track_number": track.track_number,
            "disc_number": track.disc_number,
            "year": track.year,
            "genre": track.genre,
            "bpm": track.bpm,
            "key_": track.key,
            "bucket": track.bucket,
            "fingerprint": track.fingerprint,
            "tag_completeness": track.tag_completeness,
            "tag_source": track.tag_source,
            "has_artwork": int(track.has_artwork),
            "file_mtime": file_mtime,
        }
        try:
            self._conn.execute(sql, params)
            if self._fts_available:
                self._conn.execute(
                    "DELETE FROM tracks_fts WHERE file_path = ?",
                    (str(track.file_path),),
                )
                self._conn.execute(
                    """INSERT INTO tracks_fts
                       (file_path, title, artist, album, album_artist, genre, bucket)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        str(track.file_path),
                        track.title or "",
                        track.artist or "",
                        track.album or "",
                        track.album_artist or "",
                        track.genre or "",
                        track.bucket or "",
                    ),
                )
            self._conn.commit()
        except Exception:
            logger.error("Failed to upsert track: %s", track.file_path, exc_info=True)
            raise

    def get_track(self, file_path: Path) -> Track | None:
        row = self._conn.execute(
            "SELECT * FROM tracks WHERE file_path = ?", (str(file_path),)
        ).fetchone()
        return _row_to_track(row) if row else None

    def delete_track(self, file_path: Path) -> None:
        self._conn.execute(
            "DELETE FROM tracks WHERE file_path = ?", (str(file_path),)
        )
        if self._fts_available:
            self._conn.execute(
                "DELETE FROM tracks_fts WHERE file_path = ?", (str(file_path),)
            )
        self._conn.commit()

    def get_all_tracks(self) -> list[Track]:
        rows = self._conn.execute("SELECT * FROM tracks").fetchall()
        return [_row_to_track(r) for r in rows]

    # ------------------------------------------------------------------
    # Sync helpers
    # ------------------------------------------------------------------

    def get_stale_paths(self, disk_mtimes: dict[Path, float]) -> set[Path]:
        """Return paths whose cached mtime differs from disk mtime."""
        stale: set[Path] = set()
        rows = self._conn.execute(
            "SELECT file_path, file_mtime FROM tracks"
        ).fetchall()
        cached = {Path(r["file_path"]): r["file_mtime"] for r in rows}
        for path, disk_mtime in disk_mtimes.items():
            if path in cached and cached[path] != disk_mtime:
                stale.add(path)
        return stale

    def get_removed_paths(self, disk_paths: set[Path]) -> set[Path]:
        """Return DB paths that are no longer present on disk."""
        rows = self._conn.execute("SELECT file_path FROM tracks").fetchall()
        db_paths = {Path(r["file_path"]) for r in rows}
        return db_paths - disk_paths

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str) -> list[Track]:
        if self._fts_available:
            try:
                rows = self._conn.execute(
                    """SELECT t.* FROM tracks t
                       JOIN tracks_fts f ON t.file_path = f.file_path
                       WHERE tracks_fts MATCH ?""",
                    (query,),
                ).fetchall()
                return [_row_to_track(r) for r in rows]
            except sqlite3.OperationalError:
                pass
        # Fallback: LIKE search across text columns
        like = f"%{query}%"
        rows = self._conn.execute(
            """SELECT * FROM tracks
               WHERE title LIKE ? OR artist LIKE ? OR album LIKE ?
                  OR genre LIKE ? OR bucket LIKE ?""",
            (like, like, like, like, like),
        ).fetchall()
        return [_row_to_track(r) for r in rows]

    # ------------------------------------------------------------------
    # Aggregates
    # ------------------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]

        genre_rows = self._conn.execute(
            "SELECT genre, COUNT(*) AS cnt FROM tracks WHERE genre IS NOT NULL GROUP BY genre"
        ).fetchall()
        genre_counts = {r["genre"]: r["cnt"] for r in genre_rows}

        bucket_rows = self._conn.execute(
            "SELECT bucket, COUNT(*) AS cnt FROM tracks WHERE bucket IS NOT NULL GROUP BY bucket"
        ).fetchall()
        bucket_counts = {r["bucket"]: r["cnt"] for r in bucket_rows}

        bitrate_rows = self._conn.execute(
            "SELECT bitrate, COUNT(*) AS cnt FROM tracks GROUP BY bitrate"
        ).fetchall()
        bitrate_counts = {r["bitrate"]: r["cnt"] for r in bitrate_rows}

        return {
            "total_tracks": total,
            "genre_counts": genre_counts,
            "bucket_counts": bucket_counts,
            "bitrate_counts": bitrate_counts,
        }

    def filter_tracks(self, **kwargs: Any) -> list[Track]:
        """Filter tracks by exact-match column values."""
        if not kwargs:
            return self.get_all_tracks()
        conditions = " AND ".join(f"{k} = ?" for k in kwargs)
        values = list(kwargs.values())
        rows = self._conn.execute(
            f"SELECT * FROM tracks WHERE {conditions}", values
        ).fetchall()
        return [_row_to_track(r) for r in rows]

    def close(self) -> None:
        self._conn.close()
