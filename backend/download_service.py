# backend/download_service.py
import asyncio
import logging
import os
import threading
from pathlib import Path

from backend.task_manager import manager
from backend.directory_service import get_setting
from backend.spotify_service import SpotifyService

logger = logging.getLogger(__name__)
_download_lock = threading.Lock()


def _safe_filename(s: str) -> str:
    bad = '<>:"/\\|?*'
    for ch in bad:
        s = s.replace(ch, "_")
    return s.strip().strip(".")[:180]


def run_download(task_id, urls):
    task = manager.get(task_id)
    if not task:
        return

    music_dir_setting = get_setting("music_dir")
    lyrics_dir = get_setting("lyrics_dir")

    if not music_dir_setting:
        task.status = "failed"
        task.errors.append("Music directory not set.")
        task.emit({"type": "error", "message": "Music directory not set."})
        logger.error("[task %s] Music directory not set.", task_id)
        return

    music_dir = str(Path(music_dir_setting).expanduser().resolve())
    os.makedirs(music_dir, exist_ok=True)
    if lyrics_dir:
        os.makedirs(lyrics_dir, exist_ok=True)

    logger.info("[task %s] Starting download — %d track(s)", task_id, len(urls))
    logger.info("[task %s] Music dir: %s", task_id, music_dir)
    if lyrics_dir:
        logger.info("[task %s] Lyrics dir: %s", task_id, lyrics_dir)

    task.status = "downloading"
    task.emit({"type": "started", "total": task.total})

    task.total = len(urls)
    try:
        svc = SpotifyService()
        spotdl = svc.spotdl
        if spotdl is None:
            raise RuntimeError("spotDL is not initialized.")
        asyncio.set_event_loop(spotdl.downloader.loop)
    except Exception as exc:
        task.status = "failed"
        task.errors.append(str(exc))
        logger.exception("[task %s] Could not initialize spotDL", task_id)
        task.emit({"type": "error", "message": str(exc)})
        task.emit({
            "type": "finished",
            "status": task.status,
            "completed": task.completed,
            "failed": task.failed,
        })
        return

    for index, url in enumerate(urls, 1):
        if task.is_cancelled:
            logger.info("[task %s] Cancelled by user.", task_id)
            break

        try:
            task.current_track = url
            song = svc.get_cached_song(url)
            if song is None:
                logger.info(
                    "[task %s] [%d/%d] Resolving uncached track: %s",
                    task_id, index, len(urls), url,
                )
                songs = svc.get_songs([url])
                song = next((candidate for candidate in songs if candidate.url == url), None)
            else:
                logger.info(
                    "[task %s] [%d/%d] Using preview metadata: %s",
                    task_id, index, len(urls), f"{song.artist} - {song.name}",
                )
            if song is None:
                reason = f"Could not resolve: {url}"
                task.failed += 1
                task.errors.append(reason)
                logger.warning("[task %s] %s", task_id, reason)
                task.emit({"type": "track_failed", "track": url, "error": reason})
                continue
        except Exception as exc:
            reason = f"Could not resolve {url}: {exc}"
            task.failed += 1
            task.errors.append(reason)
            logger.exception("[task %s] Failed to resolve requested URL: %s", task_id, url)
            task.emit({"type": "track_failed", "track": url, "error": str(exc)})
            continue

        if task.is_cancelled:
            logger.info("[task %s] Cancelled by user.", task_id)
            break

        label = f"{song.artist} - {song.name}"
        task.current_track = label
        task.emit({"type": "track_start", "track": label})
        logger.info("[task %s] [%d/%d] Downloading: %s", task_id, index, len(urls), label)

        try:
            with _download_lock:
                spotdl.downloader.settings["output"] = music_dir + os.sep
                results = spotdl.download_songs([song])
            path = next(
                (result_path for result_song, result_path in results
                 if result_song.url == song.url),
                None,
            )
            if path:
                task.completed += 1
                logger.info("[task %s] [%d/%d] Saved: %s", task_id, index, len(urls), path)
                if lyrics_dir:
                    _save_lyrics(song, lyrics_dir, task_id)
                task.emit({"type": "track_done", "track": label, "path": str(path)})
            else:
                reason = f"Failed: {label} (no file produced)"
                task.failed += 1
                task.errors.append(reason)
                logger.warning("[task %s] [%d/%d] %s", task_id, index, len(urls), reason)
                task.emit({"type": "track_failed", "track": label, "error": reason})
        except Exception as exc:
            reason = f"Failed: {label}: {exc}"
            task.failed += 1
            task.errors.append(reason)
            logger.exception("[task %s] Download failed for %s", task_id, label)
            task.emit({"type": "track_failed", "track": label, "error": str(exc)})

    if task.is_cancelled:
        task.status = "cancelled"
        logger.info("[task %s] Finished as CANCELLED.", task_id)
    elif task.failed and not task.completed:
        task.status = "failed"
        logger.info("[task %s] Finished as FAILED — %d track(s) failed.", task_id, task.failed)
    else:
        task.status = "completed"
        logger.info("[task %s] Finished — %d completed, %d failed.",
                    task_id, task.completed, task.failed)

    task.emit({
        "type": "finished",
        "status": task.status,
        "completed": task.completed,
        "failed": task.failed,
    })


def _save_lyrics(song, lyrics_dir, task_id):
    try:
        lyrics = song.lyrics
        if not lyrics:
            logger.info(
                "[task %s] No lyrics available for %s - %s; skipping lyrics file.",
                task_id, song.artist, song.name,
            )
            return
        fname = _safe_filename(song.name) + ".lrc"
        path = Path(lyrics_dir) / fname
        path.write_text(lyrics, encoding="utf-8")
        logger.info("[task %s] Lyrics saved: %s", task_id, path.name)
    except Exception as exc:
        logger.warning("[task %s] Lyrics save failed: %s", task_id, exc)


def start_download_async(task_id, urls):
    t = threading.Thread(target=run_download, args=(task_id, urls), daemon=True)
    t.start()
    return t