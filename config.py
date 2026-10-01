import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

CLIENT_SECRET_FILE = BASE_DIR / os.getenv("GOOGLE_CLIENT_SECRET_FILE", "client_secret.json")
TOKEN_FILE = BASE_DIR / "google_tokens.json"
OUTPUT_DIR = BASE_DIR / "output"

BASE_URL = "https://health.googleapis.com/v4"

# https://developers.google.com/health/scopes
SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.activity_and_fitness.readonly",             # steps, exercise
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",  # heart rate
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly",                            # sleep
]
