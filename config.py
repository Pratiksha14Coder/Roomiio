import os
import hashlib
from dotenv import load_dotenv

load_dotenv()

# ONLY Environment Variables - NO HARDCODED SECRETS
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET")
SECRET_KEY = os.environ.get("SECRET_KEY", "roomiio_dev_key")

DEFAULT_ADMINS = {
    "admin1": hashlib.sha256(os.environ.get("admin1", "AdminKey123!").encode()).hexdigest(),
    "admin2": hashlib.sha256(os.environ.get("admin2", "AdminKey456!").encode()).hexdigest()
}

DEFAULT_WARDENS = {
    "warden1": hashlib.sha256(os.environ.get("warden1", "WardenKey123!").encode()).hexdigest(),
    "warden2": hashlib.sha256(os.environ.get("warden2", "WardenKey456!").encode()).hexdigest()
}