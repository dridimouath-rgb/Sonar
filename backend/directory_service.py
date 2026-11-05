import sqlite3, os, shutil, threading
from queue import Queue, Empty
from pathlib import Path
from typing import Optional, Tuple
from config import DATABASE_PATH

_LOCK = threading.Lock()

def _conn():
    c = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    c.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    c.commit()
    return c

def get_setting(key: str) -> Optional[str]:
    with _LOCK:
        c = _conn()
        row = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        c.close()
        return row[0] if row else None

def set_setting(key: str, value: str):
    with _LOCK:
        c = _conn()
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
        c.commit(); c.close()

def validate_directory(path: str) -> Tuple[bool, str]:
    if not path or not path.strip():
        return False, "Path is empty."
    p = Path(path).expanduser().resolve()
    if not p.exists():
        return False, "Directory does not exist."
    if not p.is_dir():
        return False, "Not a directory."
    if not os.access(p, os.W_OK):
        return False, "Directory is not writable."
    try:
        usage = shutil.disk_usage(p)
        if usage.free < 100 * 1024 * 1024:
            return True, "Warning: less than 100 MB free."
    except OSError:
        pass
    return True, "Directory is valid and writable."

def _dialog(q: Queue, title: str):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk(); root.withdraw(); root.attributes("-topmost", True)
    try:
        sel = filedialog.askdirectory(title=title, mustexist=True)
    finally:
        root.destroy()
    q.put(sel or "")

def run_folder_picker(title: str = "Select Folder", timeout: float = 300.0) -> str:
    q: Queue = Queue()
    t = threading.Thread(target=_dialog, args=(q, title), daemon=True)
    t.start()
    try:
        return q.get(timeout=timeout)
    except Empty:
        return ""
