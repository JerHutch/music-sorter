from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import acoustid
except ImportError:
    acoustid = None

try:
    import musicbrainzngs
    musicbrainzngs.set_useragent("music-sorter", "0.1", "https://github.com/")
except ImportError:
    musicbrainzngs = None

_API_KEY = "ACOUSTID_API_KEY"


def generate_fingerprint(path: Path) -> str | None:
    """Generate a Chromaprint audio fingerprint. Returns fingerprint string or None."""
    logger.debug("Generating fingerprint: %s", path)
    try:
        result = subprocess.run(
            ["fpcalc", "-raw", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            logger.warning("fpcalc returned non-zero exit code for: %s", path)
            return None
        for line in result.stdout.strip().split("\n"):
            if line.startswith("FINGERPRINT="):
                return line.split("=", 1)[1]
        return None
    except subprocess.TimeoutExpired:
        logger.error("fpcalc timed out for: %s", path)
        return None
    except FileNotFoundError:
        logger.error("fpcalc not found — install Chromaprint to enable fingerprinting")
        return None


def _fetch_musicbrainz_details(recording_id: str) -> dict:
    """Fetch album, album_artist, track_number, year from MusicBrainz."""
    if musicbrainzngs is None:
        return {}
    try:
        result = musicbrainzngs.get_recording_by_id(
            recording_id,
            includes=["releases", "artists"],
        )
        recording = result.get("recording", {})
        releases = recording.get("release-list", [])
        if not releases:
            return {}
        release = releases[0]

        album: str | None = release.get("title")

        date_str = release.get("date", "")
        year: int | None = int(date_str[:4]) if len(date_str) >= 4 and date_str[:4].isdigit() else None

        album_artist: str | None = None
        for credit in release.get("artist-credit", []):
            if isinstance(credit, dict) and "artist" in credit:
                album_artist = credit["artist"].get("name")
                break

        track_number: int | None = None
        for medium in release.get("medium-list", []):
            track_list = medium.get("track-list", [])
            if track_list:
                num = track_list[0].get("number") or track_list[0].get("position")
                if num:
                    try:
                        track_number = int(num)
                    except (ValueError, TypeError):
                        pass
                break

        return {
            "album": album,
            "album_artist": album_artist,
            "track_number": track_number,
            "year": year,
        }
    except Exception:
        logger.warning("MusicBrainz lookup failed for recording %s", recording_id)
        return {}


def lookup_metadata(fingerprint: str, duration: float, api_key: str = _API_KEY) -> dict | None:
    """Look up track metadata via AcoustID API, then fetch extended details from MusicBrainz."""
    if acoustid is None:
        return None
    try:
        results = acoustid.match(api_key, None, None, fingerprint=fingerprint, duration=int(duration))
        for score, recording_id, title, artist in results:
            mb_details = _fetch_musicbrainz_details(recording_id)
            return {
                "score": score,
                "recording_id": recording_id,
                "title": title,
                "artist": artist,
                "album": mb_details.get("album"),
                "album_artist": mb_details.get("album_artist"),
                "track_number": mb_details.get("track_number"),
                "year": mb_details.get("year"),
            }
    except Exception:
        return None
    return None


def compute_similarity(fp1: str, fp2: str) -> float:
    """Compute similarity between two fingerprints (0.0 to 1.0)."""
    if fp1 == fp2:
        return 1.0
    try:
        ints1 = [int(x) for x in fp1.split(",")]
        ints2 = [int(x) for x in fp2.split(",")]
    except ValueError:
        common = sum(a == b for a, b in zip(fp1, fp2))
        max_len = max(len(fp1), len(fp2))
        return common / max_len if max_len > 0 else 0.0

    min_len = min(len(ints1), len(ints2))
    max_len = max(len(ints1), len(ints2))
    if max_len == 0:
        return 0.0

    matching_bits = 0
    total_bits = max_len * 32
    for i in range(min_len):
        xor = ints1[i] ^ ints2[i]
        matching_bits += 32 - bin(xor & 0xFFFFFFFF).count("1")

    return matching_bits / total_bits
