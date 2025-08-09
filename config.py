import os
from dotenv import load_dotenv

load_dotenv()

# Make configuration resilient to missing or malformed environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
DATABASE_URL = os.getenv("DATABASE_URL", "")

_admin_id_raw = os.getenv("ADMIN_ID", "")
try:
    ADMIN_ID = int(_admin_id_raw) if _admin_id_raw else None
except (TypeError, ValueError):
    ADMIN_ID = None

TELEGRAM_PAYMENTS_PROVIDER_TOKEN = os.getenv("TELEGRAM_PAYMENTS_PROVIDER_TOKEN", "")