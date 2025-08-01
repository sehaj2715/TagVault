import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
TELEGRAM_PAYMENTS_PROVIDER_TOKEN = os.getenv("TELEGRAM_PAYMENTS_PROVIDER_TOKEN")