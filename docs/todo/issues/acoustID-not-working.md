# AcoustID lookup not working

I set my api key, but I still see this in the logs for every lookup
can we add more detailed logginng to see what the error is.  

{"ts": "2026-04-12T10:47:39-0400", "level": "DEBUG", "logger": "src.core.fingerprint", "thread": "Dummy-2", "msg": "Generating fingerprint: /home/tiberius/Music/General/Canadian Folk/Stan Rogers/Northwest Passage/Stan Rogers - Northwest Passage - 05 - You Can't Stay Here.mp3"}
{"ts": "2026-04-12T10:47:39-0400", "level": "DEBUG", "logger": "urllib3.connectionpool", "thread": "Dummy-2", "msg": "Starting new HTTP connection (1): api.acoustid.org:80"}
{"ts": "2026-04-12T10:47:40-0400", "level": "DEBUG", "logger": "urllib3.connectionpool", "thread": "Dummy-2", "msg": "http://api.acoustid.org:80 \"POST /v2/lookup HTTP/1.1\" 400 75"}
{"ts": "2026-04-12T10:47:40-0400", "level": "WARNING", "logger": "src.core.fingerprint", "thread": "Dummy-2", "msg": "AcoustID lookup failed for fingerprint"}
{"ts": "2026-04-12T10:47:40-0400", "level": "DEBUG", "logger": "src.core.database", "thread": "Dummy-2", "msg": "Upserting track: /home/tiberius/Music/General/Canadian Folk/Stan Rogers/Northwest Passage/Stan Rogers - Northwest Passage - 05 - You Can't Stay Here.mp3"}


a
