# I saw this error in the logs,  Is this a problem, or an error with the file itself

```
2026-04-06 12:24:22,894 ERROR    [Dummy-1] src.gui.workers — Failed to process file: /home/tiberius/Music/General/Unknown/Maybe Memories/Unknown/Maybe Memories - Unknown - 9 - New Noise (Refused Cover).mp3
Traceback (most recent call last):
  File "/mnt/cloud/code/music-sorter/src/gui/workers.py", line 45, in run
    track = read_tags(path)
  File "/mnt/cloud/code/music-sorter/src/core/tagger.py", line 66, in read_tags
    audio = MP3(path)
  File "/mnt/cloud/code/music-sorter/.venv/lib/python3.14/site-packages/mutagen/_file.py", line 48, in __init__
    self.load(*args, **kwargs)
    ~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/mnt/cloud/code/music-sorter/.venv/lib/python3.14/site-packages/mutagen/_util.py", line 156, in wrapper
    return func(self, h, *args, **kwargs)
  File "/mnt/cloud/code/music-sorter/.venv/lib/python3.14/site-packages/mutagen/id3/_file.py", line 420, in load
    self.info = self._Info(fileobj, offset)
                ~~~~~~~~~~^^^^^^^^^^^^^^^^^
  File "/mnt/cloud/code/music-sorter/.venv/lib/python3.14/site-packages/mutagen/_util.py", line 185, in wrapper
    return func(*args, **kwargs)
  File "/mnt/cloud/code/music-sorter/.venv/lib/python3.14/site-packages/mutagen/mp3/__init__.py", line 401, in __init__
    raise HeaderNotFoundError("can't sync to MPEG frame")
mutagen.mp3.HeaderNotFoundError: can't sync to MPEG frame
```
