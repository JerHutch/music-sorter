from __future__ import annotations
import logging
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

try:
    import librosa
except ImportError:
    librosa = None

_CAMELOT_MAJOR = {
    0: "8B", 1: "3B", 2: "10B", 3: "5B", 4: "12B", 5: "7B",
    6: "2B", 7: "9B", 8: "4B", 9: "11B", 10: "6B", 11: "1B",
}
_CAMELOT_MINOR = {
    0: "5A", 1: "12A", 2: "7A", 3: "2A", 4: "9A", 5: "4A",
    6: "11A", 7: "6A", 8: "1A", 9: "8A", 10: "3A", 11: "10A",
}


def _pitch_class_to_camelot(pitch_class: int, is_major: bool) -> str:
    if is_major:
        return _CAMELOT_MAJOR[pitch_class]
    return _CAMELOT_MINOR[pitch_class]


def detect_bpm(path: Path, duration_limit: float = 60.0) -> float | None:
    if librosa is None:
        return None
    logger.debug("Detecting BPM: %s", path)
    try:
        y, sr = librosa.load(str(path), duration=duration_limit, sr=22050, mono=True)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        if isinstance(tempo, np.ndarray):
            tempo = float(tempo[0])
        return round(float(tempo), 1)
    except Exception:
        logger.error("BPM detection failed: %s", path, exc_info=True)
        return None


def detect_key(path: Path, duration_limit: float = 60.0) -> str | None:
    if librosa is None:
        return None
    logger.debug("Detecting key: %s", path)
    try:
        y, sr = librosa.load(str(path), duration=duration_limit, sr=22050, mono=True)
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        chroma_avg = np.mean(chroma, axis=1)

        major_profile = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09,
                                   2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
        minor_profile = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53,
                                   2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

        best_corr = -2.0
        best_pitch = 0
        best_is_major = True

        for shift in range(12):
            shifted = np.roll(chroma_avg, -shift)
            major_corr = float(np.corrcoef(shifted, major_profile)[0, 1])
            minor_corr = float(np.corrcoef(shifted, minor_profile)[0, 1])

            if major_corr > best_corr:
                best_corr = major_corr
                best_pitch = shift
                best_is_major = True
            if minor_corr > best_corr:
                best_corr = minor_corr
                best_pitch = shift
                best_is_major = False

        return _pitch_class_to_camelot(best_pitch, best_is_major)
    except Exception:
        logger.error("Key detection failed: %s", path, exc_info=True)
        return None
