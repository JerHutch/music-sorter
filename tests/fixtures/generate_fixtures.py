"""Generate minimal MP3 test fixtures with known tags.

Run once: python tests/fixtures/generate_fixtures.py
Creates small valid MP3 files in tests/fixtures/ for use in unit tests.
"""

from pathlib import Path

from mutagen.id3 import ID3, TALB, TBPM, TIT2, TPE1, TPE2, TPOS, TRCK, TYER, TCON, TXXX
from mutagen.mp3 import MP3


FIXTURES_DIR = Path(__file__).parent

# Minimal valid MP3 frame (silence, ~0.026s, 128kbps)
MP3_FRAME = (
    b"\xff\xfb\x90\x00"  # MPEG1 Layer3 128kbps 44100Hz stereo
    + b"\x00" * 413       # pad to full frame size (417 bytes for this config)
)


def make_mp3(filename: str, tags: dict | None = None, frame_count: int = 10) -> Path:
    """Create a minimal MP3 file with optional ID3 tags."""
    path = FIXTURES_DIR / filename
    with open(path, "wb") as f:
        for _ in range(frame_count):
            f.write(MP3_FRAME)

    if tags:
        audio = MP3(path)
        audio.add_tags()
        id3 = audio.tags

        tag_map = {
            "title": lambda v: TIT2(encoding=3, text=[v]),
            "artist": lambda v: TPE1(encoding=3, text=[v]),
            "album_artist": lambda v: TPE2(encoding=3, text=[v]),
            "album": lambda v: TALB(encoding=3, text=[v]),
            "track_number": lambda v: TRCK(encoding=3, text=[str(v)]),
            "disc_number": lambda v: TPOS(encoding=3, text=[str(v)]),
            "year": lambda v: TYER(encoding=3, text=[str(v)]),
            "genre": lambda v: TCON(encoding=3, text=[v]),
            "bpm": lambda v: TBPM(encoding=3, text=[str(v)]),
        }

        for key, value in tags.items():
            if key == "bucket":
                id3.add(TXXX(encoding=3, desc="MUSIC_SORTER_BUCKET", text=[value]))
            elif key in tag_map:
                id3.add(tag_map[key](value))

        audio.save()

    return path


def main():
    make_mp3("tagged_full.mp3", {
        "title": "Blue Monday",
        "artist": "New Order",
        "album_artist": "New Order",
        "album": "Power, Corruption & Lies",
        "track_number": 5,
        "disc_number": 1,
        "year": 1983,
        "genre": "Synth-Pop",
        "bpm": 130,
        "bucket": "DJ Music",
    })

    make_mp3("tagged_partial.mp3", {
        "title": "Strobe",
        "artist": "Deadmau5",
        "genre": "Progressive House",
    })

    make_mp3("untagged.mp3")

    make_mp3("tagged_full_dupe.mp3", {
        "title": "Blue Monday",
        "artist": "New Order",
        "album": "Power, Corruption & Lies",
        "genre": "Synth-Pop",
    }, frame_count=5)

    print(f"Fixtures created in {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
