import logging

import requests

logger = logging.getLogger(__name__)

_LRCLIB_API = "https://lrclib.net/api"
_USER_AGENT = "SONORA/1.0 (local app)"


def fetch_lyrics(song, timeout=10) -> str | None:
    track_name = getattr(song, "name", "")
    artist_name = getattr(song, "artist", "")
    album_name = getattr(song, "album_name", None)
    duration = getattr(song, "duration", 0) or 0
    headers = {"User-Agent": _USER_AGENT}

    params = {
        "track_name": track_name,
        "artist_name": artist_name,
        "duration": duration,
    }
    if album_name:
        params["album_name"] = album_name

    try:
        response = requests.get(
            f"{_LRCLIB_API}/get", params=params, headers=headers, timeout=timeout
        )
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict):
                lyrics = data.get("syncedLyrics") or data.get("plainLyrics")
                if lyrics:
                    return lyrics
    except (requests.RequestException, ValueError) as exc:
        logger.warning("LRCLIB lyrics lookup failed: %s", exc)

    try:
        response = requests.get(
            f"{_LRCLIB_API}/search",
            params={"track_name": track_name, "artist_name": artist_name},
            headers=headers,
            timeout=timeout,
        )
        if response.status_code != 200:
            return None

        results = response.json()
        if not isinstance(results, list):
            return None
        if duration:
            matching_results = []
            for result in results:
                if not isinstance(result, dict) or result.get("duration") is None:
                    continue
                try:
                    matches_duration = (
                        abs(float(result["duration"]) - float(duration)) <= 3
                    )
                except (TypeError, ValueError, OverflowError):
                    continue
                if matches_duration:
                    matching_results.append(result)
            results = matching_results
        else:
            results = [result for result in results if isinstance(result, dict)]

        for key in ("syncedLyrics", "plainLyrics"):
            lyrics = next((result.get(key) for result in results if result.get(key)), None)
            if lyrics:
                return lyrics
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("LRCLIB lyrics lookup failed: %s", exc)

    return None
