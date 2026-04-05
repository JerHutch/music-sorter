from __future__ import annotations

from pathlib import Path

from mutagen.id3 import (
    ID3,
    TALB,
    TBPM,
    TCON,
    TDRC,
    TIT2,
    TPE1,
    TPE2,
    TPOS,
    TRCK,
    TXXX,
    ID3NoHeaderError,
)
from mutagen.mp3 import MP3

from src.core.models import Track


def _get_text(tags, key: str) -> str | None:
    frame = tags.get(key)
    if frame and frame.text:
        val = str(frame.text[0]).strip()
        return val if val else None
    return None


def _get_int(tags, key: str) -> int | None:
    text = _get_text(tags, key)
    if text is None:
        return None
    text = text.split("/")[0]
    try:
        return int(text)
    except ValueError:
        return None


def _get_float(tags, key: str) -> float | None:
    text = _get_text(tags, key)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _get_txxx(tags, desc: str) -> str | None:
    key = f"TXXX:{desc}"
    return _get_text(tags, key)


def read_tags(path: Path) -> Track:
    audio = MP3(path)
    tags = audio.tags or {}

    return Track(
        file_path=path,
        file_size=path.stat().st_size,
        bitrate=audio.info.bitrate // 1000 if audio.info.bitrate else 0,
        duration=audio.info.length or 0.0,
        title=_get_text(tags, "TIT2"),
        artist=_get_text(tags, "TPE1"),
        album_artist=_get_text(tags, "TPE2"),
        album=_get_text(tags, "TALB"),
        track_number=_get_int(tags, "TRCK"),
        disc_number=_get_int(tags, "TPOS"),
        year=_get_int(tags, "TDRC") or _get_int(tags, "TYER"),
        genre=_get_text(tags, "TCON"),
        bpm=_get_float(tags, "TBPM"),
        key=_get_txxx(tags, "INITIAL_KEY"),
        bucket=_get_txxx(tags, "MUSIC_SORTER_BUCKET"),
        has_artwork=any(k.startswith("APIC") for k in tags),
    )


def write_tags(
    path: Path, track: Track, fields: list[str], dry_run: bool = False
) -> None:
    if dry_run:
        return

    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()

    field_to_frame = {
        "title": lambda: TIT2(encoding=3, text=[track.title]) if track.title else None,
        "artist": lambda: (
            TPE1(encoding=3, text=[track.artist]) if track.artist else None
        ),
        "album_artist": lambda: (
            TPE2(encoding=3, text=[track.album_artist]) if track.album_artist else None
        ),
        "album": lambda: TALB(encoding=3, text=[track.album]) if track.album else None,
        "track_number": lambda: (
            TRCK(encoding=3, text=[str(track.track_number)])
            if track.track_number is not None
            else None
        ),
        "disc_number": lambda: (
            TPOS(encoding=3, text=[str(track.disc_number)])
            if track.disc_number is not None
            else None
        ),
        "year": lambda: (
            TDRC(encoding=3, text=[str(track.year)]) if track.year is not None else None
        ),
        "genre": lambda: TCON(encoding=3, text=[track.genre]) if track.genre else None,
        "bpm": lambda: (
            TBPM(encoding=3, text=[str(track.bpm)]) if track.bpm is not None else None
        ),
    }

    txxx_fields = {
        "bucket": "MUSIC_SORTER_BUCKET",
        "key": "INITIAL_KEY",
    }

    for field in fields:
        if field in field_to_frame:
            frame = field_to_frame[field]()
            if frame:
                id3.add(frame)
        elif field in txxx_fields:
            value = getattr(track, field, None)
            if value is not None:
                id3.add(TXXX(encoding=3, desc=txxx_fields[field], text=[str(value)]))

    id3.save(path)
