import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_BASE_URL = os.getenv("API_BASE_URL")
SQLITE_PATH = os.getenv("SQLITE_PATH", "bot_database.db")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
REQUEST_TIMEOUT_SEC = int(os.getenv("REQUEST_TIMEOUT_SEC", "60"))

# Validation
if not BOT_TOKEN:
    print("Warning: BOT_TOKEN is not set.")
if not API_BASE_URL:
    print("Warning: API_BASE_URL is not set.")
