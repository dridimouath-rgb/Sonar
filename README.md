# SONORA

SONORA is a local web interface for previewing Spotify playlists and downloading
selected tracks to folders on your computer. The Flask server and browser are
intended to run on the same machine; the application uses a native folder picker
to choose music and optional lyrics directories.

## Requirements

- Python 3.10 or newer
- FFmpeg available on your `PATH` (required by spotDL for audio conversion)
- Tkinter for the native folder picker (on Debian/Ubuntu, install `python3-tk`)

## Install

```bash
git clone https://github.com/<YOUR-USERNAME>/SONORA.git
cd SONORA
python -m venv .venv
```

Activate the virtual environment:

```bash
# Linux or macOS
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

Install Python dependencies and configure the Flask secret:

```bash
python -m pip install -r requirements.txt
cp .env.example .env
```

Set `FLASK_SECRET_KEY` in `.env` to a private random value. Generate one with:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Keep `.env` private; it is excluded from Git.

## Run

```bash
python app.py
```

Open <http://127.0.0.1:5000> in a browser on the same computer. Choose your
music and optional lyrics folders in **Storage & Lyrics**, preview a Spotify
link, select tracks, and start a download.

SONORA stores settings and task state locally under `instance/` and writes its
application log under `logs/`; these runtime files are not included in Git.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Important

SONORA is a local application, not a hosted public website. Its directory picker
selects folders on the computer running the server, so exposing this server to
the public internet is not a supported deployment setup.

Use the application and its dependencies only in compliance with applicable
copyright law and the terms of the services and content providers you use.
SONORA does not provide Spotify-native lyrics access; it saves lyric text only
when it is already present on a track object.
