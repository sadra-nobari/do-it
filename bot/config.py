import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from project root
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Tehran").strip()
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "do_it.db")).strip()
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None
