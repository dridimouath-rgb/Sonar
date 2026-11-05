import os, logging
from pathlib import Path
from mutagen import File as MutagenFile

logger = logging.getLogger(__name__)

AUDIO_EXTS = {".mp3", ".flac", ".m4a", ".opus", ".ogg"}

def scan_library(music_dir: str):
    if not music_dir or not os.path.isdir(music_dir):
        return []
    items = []
    for root, _, files in os.walk(music_dir):
        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in AUDIO_EXTS:
                continue
            full = os.path.join(root, f)
            try:
                audio = MutagenFile(full, easy=True)
                duration = int(audio.info.length) if audio and audio.info else 0
                title = (audio.get("title", [Path(f).stem])[0] if audio else Path(f).stem)
                artist = (audio.get("artist", ["Unknown"])[0] if audio else "Unknown")
                album = (audio.get("album", [""])[0] if audio else "")
            except Exception:
                title, artist, album, duration = Path(f).stem, "Unknown", "", 0
            items.append({
                "path": full, "filename": f, "title": title,
                "artist": artist, "album": album,
                "duration": duration, "format": ext.lstrip("."),
                "size": os.path.getsize(full),
            })
    items.sort(key=lambda x: (x["artist"].lower(), x["title"].lower()))
    return items
