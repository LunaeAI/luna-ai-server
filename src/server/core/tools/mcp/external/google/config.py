import logging
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN_PATH = os.getenv("GOOGLE_TOKEN_FILE")
CLIENT_SECRETS_PATH = os.getenv("GOOGLE_CLIENT_SECRETS_FILE")

logger = logging.getLogger(__name__)

logger.error(f"Google TOKEN_PATH: {TOKEN_PATH}")
logger.error(f"Google CLIENT_SECRETS_PATH: {CLIENT_SECRETS_PATH}")

# --- IMPORTANT --- After updating this, you MUST delete your old token.json and re-run get_credentials.py
SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/drive',
]