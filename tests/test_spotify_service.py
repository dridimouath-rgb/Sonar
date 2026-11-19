import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.spotify_service import SpotifyService


class SpotifyServiceTests(unittest.TestCase):
    def make_song(self, lyrics=None):
        return SimpleNamespace(
            name="Track",
            artist="Artist",
            album_name="Album",
            artists=["Artist"],
            album_artist="Artist",
            duration=180,
            cover_url=None,
            year=2024,
            track_number=1,
            song_id="song-id",
            url="https://open.spotify.com/track/song-id",
            lyrics=lyrics,
        )

    def test_analyze_marks_tracks_when_lrclib_lyrics_are_found(self):
        song = self.make_song()
        service = object.__new__(SpotifyService)
        with (
            patch("backend.spotify_service.get_simple_songs", return_value=[song]),
            patch("backend.spotify_service.fetch_lyrics", return_value="[00:01.00]Hello") as fetch,
            patch.object(SpotifyService, "_cache_songs"),
        ):
            result = service.analyze(song.url)

        self.assertTrue(result["tracks"][0]["has_lyrics"])
        self.assertEqual(song.lyrics, "[00:01.00]Hello")
        fetch.assert_called_once_with(song)

    def test_analyze_does_not_repeat_lookup_for_existing_song_lyrics(self):
        song = self.make_song(lyrics="Existing lyrics")
        service = object.__new__(SpotifyService)
        with (
            patch("backend.spotify_service.get_simple_songs", return_value=[song]),
            patch("backend.spotify_service.fetch_lyrics") as fetch,
            patch.object(SpotifyService, "_cache_songs"),
        ):
            result = service.analyze(song.url)

        self.assertTrue(result["tracks"][0]["has_lyrics"])
        fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
