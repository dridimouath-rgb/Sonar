import asyncio
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.download_service import _save_lyrics, run_download


class FakeTask:
    def __init__(self, total):
        self.status = "pending"
        self.total = total
        self.completed = 0
        self.failed = 0
        self.current_track = None
        self.errors = []
        self.events = []
        self.is_cancelled = False

    def emit(self, event):
        self.events.append(event.copy())


class FakeSpotifyService:
    def __init__(
        self, loop, songs, operations, expected_output, fail_urls=(), cache_miss_urls=()
    ):
        self.spotdl = SimpleNamespace(
            downloader=SimpleNamespace(loop=loop, settings={"output": "default"}),
            download_songs=self.download_songs,
        )
        self._songs = songs
        self._operations = operations
        self._expected_output = expected_output
        self._fail_urls = set(fail_urls)
        self._cache_miss_urls = set(cache_miss_urls)

    def get_songs(self, urls):
        if asyncio.get_event_loop() is not self.spotdl.downloader.loop:
            raise AssertionError("spotDL loop is not attached during resolution")
        self._operations.extend(("resolve", url) for url in urls)
        return [self._songs[url] for url in urls if url in self._songs]

    def get_cached_song(self, url):
        self._operations.append(("cached", url))
        if url in self._cache_miss_urls:
            return None
        return self._songs.get(url)

    def download_songs(self, songs):
        song = songs[0]
        self._operations.append(("download", song.url))
        if asyncio.get_event_loop() is not self.spotdl.downloader.loop:
            raise AssertionError("spotDL loop is not attached to the worker thread")
        if self.spotdl.downloader.settings["output"] != self._expected_output + os.sep:
            raise AssertionError("spotDL output directory does not match the selected music directory")
        if song.url in self._fail_urls:
            raise RuntimeError("test download failure")
        return [(song, Path(f"/music/{song.name}.mp3"))]


class DownloadServiceTests(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.addCleanup(self.loop.close)
        self.addCleanup(asyncio.set_event_loop, None)

    def run_task(self, urls, fail_urls=(), cache_miss_urls=()):
        task = FakeTask(len(urls))
        operations = []
        songs = {
            url: SimpleNamespace(url=url, artist="Artist", name=f"Track {i}", lyrics=None)
            for i, url in enumerate(urls, 1)
        }
        with tempfile.TemporaryDirectory() as music_dir:
            service = FakeSpotifyService(
                self.loop, songs, operations, music_dir, fail_urls, cache_miss_urls
            )
            with (
                patch("backend.download_service.manager.get", return_value=task),
                patch(
                    "backend.download_service.get_setting",
                    side_effect=lambda key: music_dir if key == "music_dir" else None,
                ),
                patch("backend.download_service.SpotifyService", return_value=service),
            ):
                worker = threading.Thread(target=run_download, args=("task-id", urls))
                worker.start()
                worker.join(timeout=5)
                self.assertFalse(worker.is_alive(), "download worker did not finish")

        return task, operations

    def test_resolves_and_downloads_each_track_before_resolving_the_next(self):
        urls = ["spotify:track:one", "spotify:track:two"]
        task, operations = self.run_task(urls)

        self.assertEqual(
            operations,
            [
                ("cached", urls[0]),
                ("download", urls[0]),
                ("cached", urls[1]),
                ("download", urls[1]),
            ],
        )
        self.assertEqual((task.completed, task.failed, task.status), (2, 0, "completed"))

    def test_one_track_failure_does_not_stop_later_tracks(self):
        urls = ["spotify:track:one", "spotify:track:two"]
        task, operations = self.run_task(urls, fail_urls={urls[0]})

        self.assertEqual(
            operations,
            [
                ("cached", urls[0]),
                ("download", urls[0]),
                ("cached", urls[1]),
                ("download", urls[1]),
            ],
        )
        self.assertEqual((task.completed, task.failed, task.status), (1, 1, "completed"))
        failed_events = [event for event in task.events if event["type"] == "track_failed"]
        self.assertEqual(len(failed_events), 1)
        self.assertIn("test download failure", failed_events[0]["error"])

    def test_uncached_track_falls_back_to_spotify_resolution(self):
        url = "spotify:track:uncached"
        task, operations = self.run_task([url], cache_miss_urls={url})

        self.assertEqual(
            operations,
            [("cached", url), ("resolve", url), ("download", url)],
        )
        self.assertEqual((task.completed, task.failed, task.status), (1, 0, "completed"))

    def test_missing_lyrics_do_not_create_file(self):
        song = SimpleNamespace(
            name="Track",
            artist="Artist",
            artists=["Artist"],
            duration=180,
            lyrics=None,
        )
        with tempfile.TemporaryDirectory() as lyrics_dir:
            _save_lyrics(song, lyrics_dir, "task-id")

            self.assertEqual(list(Path(lyrics_dir).iterdir()), [])

    def test_available_lyrics_are_saved_by_track_title(self):
        song = SimpleNamespace(
            name="Track: Title",
            artist="Artist",
            lyrics="[00:01.00]Available lyrics",
        )
        with tempfile.TemporaryDirectory() as lyrics_dir:
            _save_lyrics(song, lyrics_dir, "task-id")

            path = Path(lyrics_dir) / "Track_ Title.lrc"
            self.assertEqual(path.read_text(encoding="utf-8"), song.lyrics)


if __name__ == "__main__":
    unittest.main()
