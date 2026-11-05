# backend/spotify_service.py
import logging
import re
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

from spotdl import Spotdl
from spotdl.utils.search import get_simple_songs
from spotdl.types.song import Song

logger = logging.getLogger(__name__)

class SpotifyServiceError(Exception):
    pass

class SpotifyService:
    _instance = None
    _spotdl = None
    _song_cache_limit = 2000
    _song_cache: OrderedDict[str, Song]
    _song_cache_lock: threading.Lock

    def __new__(cls):
        # Singleton pattern to prevent "A spotify client has already been initialized"
        if cls._instance is None:
            cls._instance = super(SpotifyService, cls).__new__(cls)
            cls._instance._song_cache = OrderedDict()
            cls._instance._song_cache_lock = threading.Lock()
            logger.info("Initializing spotDL client...")
            cls._spotdl = Spotdl(
                client_id="dummy",
                client_secret="dummy",
                use_official_api=False,
                no_cache=False,
                downloader_settings={"lyrics_providers": []},
            )
        return cls._instance

    def analyze(self, url: str):
        try:
            if "/playlist/" in url.lower():
                title, owner, cover_url, songs = _read_playlist(url)
            else:
                songs = get_simple_songs([url])
                title = owner = cover_url = None
        except Exception as exc:
            logger.exception("Could not read Spotify track metadata")
            raise SpotifyServiceError(f"Could not analyze URL: {exc}") from exc
        
        if not songs:
            raise SpotifyServiceError("No tracks found for the provided URL.")

        self._cache_songs(songs)
        tracks = [{
            "song_id": s.song_id, "name": s.name, "artist": s.artist,
            "artists": s.artists, "album_name": s.album_name,
            "album_artist": s.album_artist, "duration": s.duration,
            "cover_url": s.cover_url, "year": s.year,
            "track_number": s.track_number, "url": s.url,
        } for s in songs]
        
        first = songs[0]
        return {
            "type": _infer_type(url),
            "title": title or getattr(first, "list_name", None) or first.album_name or first.name or "Spotify tracks",
            "owner": owner or getattr(first, "album_artist", None) or first.artist,
            "cover_url": cover_url or first.cover_url,
            "total_tracks": len(tracks),
            "total_duration": sum(t["duration"] for t in tracks),
            "tracks": tracks,
        }

    def get_songs(self, urls):
        assert self._spotdl is not None
        return self._spotdl.search(urls)

    def get_cached_song(self, url: str):
        with self._song_cache_lock:
            song = self._song_cache.get(url)
            if song is not None:
                self._song_cache.move_to_end(url)
            return song

    def _cache_songs(self, songs):
        with self._song_cache_lock:
            for song in songs:
                self._song_cache[song.url] = song
                self._song_cache.move_to_end(song.url)
            while len(self._song_cache) > self._song_cache_limit:
                self._song_cache.popitem(last=False)

    @property
    def spotdl(self):
        return self._spotdl


def _read_playlist(url: str):
    from spotapi import PublicPlaylist
    from spotapi.http.request import TLSClient
    from SpotipyFree.Formatter import SpotifyFormatter

    normalized_url = re.sub(r"/intl-\w+/", "/", url)
    playlist_id = urlsplit(normalized_url).path.rstrip("/").split("/")[-1]
    playlist_response = PublicPlaylist(playlist_id).get_playlist_info(limit=343)
    playlist = playlist_response["data"]["playlistV2"]
    content = playlist["content"]
    raw_tracks = list(content["items"])
    total_count = content["totalCount"]
    offsets = range(343, total_count, 343)

    def fetch_page(offset):
        client = TLSClient("chrome120", "", auto_retries=3)
        try:
            page = PublicPlaylist(playlist_id, client=client).get_playlist_info(
                limit=343, offset=offset
            )["data"]["playlistV2"]["content"]
            return page["items"]
        finally:
            client.close()

    if offsets:
        with ThreadPoolExecutor(max_workers=min(3, len(offsets))) as executor:
            for page_tracks in executor.map(fetch_page, offsets):
                raw_tracks.extend(page_tracks)

    images = (playlist.get("images") or {}).get("items", [])
    playlist_images = images[-1].get("sources", []) if images else []
    cover_url = max(
        playlist_images,
        key=lambda image: (image.get("width") or 0) * (image.get("height") or 0),
        default={},
    ).get("url")

    songs = []
    for position, raw_track in enumerate(raw_tracks, 1):
        try:
            track = SpotifyFormatter.formatPlaylistTrack(raw_track)["track"]
            if track.get("type") != "track" or not track.get("id"):
                continue

            track_v2 = raw_track["itemV2"]["data"]
            album = track_v2.get("albumOfTrack") or {}
            album_art = (album.get("coverArt") or {}).get("sources", [])
            album_cover = max(
                album_art,
                key=lambda image: (image.get("width") or 0) * (image.get("height") or 0),
                default={},
            ).get("url")
            artists = [artist.get("name", "") for artist in track.get("artists", [])]
            album_artists = (album.get("artists") or {}).get("items", [])
            release_date = (album.get("date") or {}).get("isoString", "")
            songs.append(Song.from_missing_data(
                name=track["name"],
                artists=artists,
                artist=artists[0] if artists else "Unknown",
                album_id=(album.get("uri") or "").removeprefix("spotify:album:"),
                album_name=album.get("name"),
                album_artist=album_artists[0].get("profile", {}).get("name") if album_artists else None,
                duration=int(track["duration_ms"] / 1000),
                year=release_date[:4] if release_date else None,
                date=release_date,
                track_number=track.get("track_number"),
                song_id=track["id"],
                explicit=track.get("explicit", False),
                url=track["external_urls"]["spotify"],
                cover_url=album_cover or cover_url,
                list_name=playlist.get("name"),
                list_url=normalized_url,
                list_position=position,
                list_length=total_count,
            ))
        except (KeyError, TypeError, IndexError) as exc:
            logger.warning("Skipping malformed track %d in playlist %s: %s", position, playlist_id, exc)

    owner = (playlist.get("ownerV2") or {}).get("data", {}).get("name")
    return playlist.get("name"), owner, cover_url, songs


def _infer_type(url: str) -> str:
    u = url.lower()
    if "/playlist/" in u:
        return "playlist"
    if "/album/" in u:
        return "album"
    if "/track/" in u:
        return "track"
    return "unknown"