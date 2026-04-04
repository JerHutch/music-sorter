from __future__ import annotations

import subprocess
from pathlib import Path

try:
    import acoustid
except ImportError:
    acoustid = None

_API_KEY = "ACOUSTID_API_KEY"


def generate_fingerprint(path: Path) -> str | None:
    """Generate a Chromaprint audio fingerprint. Returns fingerprint string or None."""
    try:
        result = subprocess.run(
            ["fpcalc", "-raw", str(path)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.strip().split("\n"):
            if line.startswith("FINGERPRINT="):
                return line.split("=", 1)[1]
        return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def lookup_metadata(fingerprint: str, duration: float, api_key: str = _API_KEY) -> dict | None:
    """Look up track metadata via AcoustID API."""
    if acoustid is None:
        return None
    try:
        results = acoustid.match(api_key, None, None, fingerprint=fingerprint, duration=int(duration))
        for score, recording_id, title, artist in results:
            return {
                "score": score,
                "recording_id": recording_id,
                "title": title,
                "artist": artist,
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
        # Not in raw integer format — fall back to string comparison
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
