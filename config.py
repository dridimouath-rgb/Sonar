import os
import secrets
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
LOGS_DIR = BASE_DIR / "logs"
DATABASE_PATH = INSTANCE_DIR / "sonora.db"

INSTANCE_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

FLASK_SECRET_KEY = os.getenv("FLASK_SECRET_KEY") or secrets.token_hex(32)
