from __future__ import annotations
import logging
from pathlib import Path
from mutagen.id3 import ID3, ID3NoHeaderError, APIC
from mutagen.mp3 import MP3

logger = logging.getLogger(__name__)

try:
    import musicbrainzngs
    musicbrainzngs.set_useragent("MusicSorter", "0.1.0", "https://github.com/JerHutch/music-sorter")
except ImportError:
    musicbrainzngs = None

_COVER_CANDIDATES = [
    "cover.jpg", "cover.png",
    "folder.jpg", "folder.png",
    "artwork.jpg", "artwork.png",
    "front.jpg", "front.png",
]


def find_local_artwork(path: Path) -> bytes | None:
    """Search the MP3's directory for common cover art filenames (case-insensitive)."""
    directory = path.parent
    try:
        files = {f.name.lower(): f for f in directory.iterdir() if f.is_file()}
    except OSError:
        return None
    for name in _COVER_CANDIDATES:
        if name in files:
            return files[name].read_bytes()
    return None


def read_artwork(path: Path) -> bytes | None:
    """Return raw bytes of the first embedded APIC frame, or None if absent."""
    try:
        audio = MP3(path)
        tags = audio.tags or {}
        for key in tags:
            if key.startswith("APIC"):
                return tags[key].data
        return None
    except Exception:
        logger.warning("read_artwork: could not read %s", path)
        return None


def has_artwork(path: Path) -> bool:
    try:
        audio = MP3(path)
        tags = audio.tags or {}
        return any(k.startswith("APIC") for k in tags)
    except Exception:
        return False

def embed_artwork(path: Path, image_data: bytes, dry_run: bool = False) -> None:
    if dry_run:
        return
    logger.debug("Embedding artwork in: %s", path)
    try:
        id3 = ID3(path)
    except ID3NoHeaderError:
        id3 = ID3()
    mime = "image/png" if image_data[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"
    id3.add(APIC(encoding=3, mime=mime, type=3, desc="Front Cover", data=image_data))
    id3.save(path)

def search_cover_art(artist: str, album: str) -> bytes | None:
    if musicbrainzngs is None:
        return None
    logger.info("Searching MusicBrainz for artwork: %s — %s", artist, album)
    try:
        results = musicbrainzngs.search_releases(artist=artist, release=album, limit=5)
        releases = results.get("release-list", [])
        if not releases:
            logger.warning("No MusicBrainz releases found for: %s — %s", artist, album)
            return None
        image = musicbrainzngs.get_image_front(releases[0]["id"])
        logger.info("Artwork found for: %s — %s", artist, album)
        return image
    except Exception:
        logger.error("MusicBrainz lookup failed for: %s — %s", artist, album, exc_info=True)
        return None
