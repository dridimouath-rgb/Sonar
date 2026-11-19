import unittest
from types import SimpleNamespace
from unittest.mock import patch

from backend.lyrics_service import fetch_lyrics


class LyricsServiceTests(unittest.TestCase):
    def test_get_returns_synced_lyrics_and_sends_track_metadata(self):
        song = SimpleNamespace(
            name="Track",
            artist="Artist",
            album_name="Album",
            duration=180,
        )
        response = SimpleNamespace(
            status_code=200,
            json=lambda: {
                "syncedLyrics": "[00:01.00]Synced",
                "plainLyrics": "Plain",
            },
        )
        with patch("backend.lyrics_service.requests.get", return_value=response) as get:
            lyrics = fetch_lyrics(song)

        self.assertEqual(lyrics, "[00:01.00]Synced")
        get.assert_called_once_with(
            "https://lrclib.net/api/get",
            params={
                "track_name": "Track",
                "artist_name": "Artist",
                "duration": 180,
                "album_name": "Album",
            },
            headers={"User-Agent": "SONORA/1.0 (local app)"},
            timeout=10,
        )

    def test_search_filters_by_duration_and_prefers_synced_lyrics(self):
        song = SimpleNamespace(
            name="Track",
            artist="Artist",
            album_name=None,
            duration=180,
        )
        get_response = SimpleNamespace(status_code=404)
        search_response = SimpleNamespace(
            status_code=200,
            json=lambda: [
                {"duration": "unknown", "syncedLyrics": "Malformed duration"},
                {"duration": 190, "syncedLyrics": "Out of range"},
                {"duration": 183, "plainLyrics": "Plain"},
                {"duration": 181, "syncedLyrics": "Synced"},
            ],
        )
        with patch(
            "backend.lyrics_service.requests.get",
            side_effect=[get_response, search_response],
        ) as get:
            lyrics = fetch_lyrics(song)

        self.assertEqual(lyrics, "Synced")
        self.assertEqual(get.call_count, 2)
        self.assertEqual(
            get.call_args_list[1].kwargs["params"],
            {"track_name": "Track", "artist_name": "Artist"},
        )

    def test_search_skips_duration_filter_when_track_duration_is_zero(self):
        song = SimpleNamespace(
            name="Track",
            artist="Artist",
            album_name=None,
            duration=0,
        )
        get_response = SimpleNamespace(status_code=404)
        search_response = SimpleNamespace(
            status_code=200,
            json=lambda: [{"duration": 500, "plainLyrics": "Plain"}],
        )
        with patch(
            "backend.lyrics_service.requests.get",
            side_effect=[get_response, search_response],
        ):
            lyrics = fetch_lyrics(song)

        self.assertEqual(lyrics, "Plain")


if __name__ == "__main__":
    unittest.main()
