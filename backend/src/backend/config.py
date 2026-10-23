import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BACKEND_DIR / ".env")

DATABASE_DIR = Path("/tmp") if os.getenv("VERCEL") else BACKEND_DIR / "data"
DATABASE_PATH = Path(os.getenv("DATABASE_PATH", str(DATABASE_DIR / "wind.db")))
if not DATABASE_PATH.is_absolute():
    DATABASE_PATH = BACKEND_DIR / DATABASE_PATH

ELEXON_API_BASE_URL = os.getenv(
    "ELEXON_API_BASE_URL",
    "https://data.elexon.co.uk/bmrs/api/v1/datasets",
).rstrip("/")

ELEXON_TIMEOUT_SECONDS = float(os.getenv("ELEXON_TIMEOUT_SECONDS", "60"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000",
    ).split(",")
    if origin.strip()
]

FORECAST_HORIZON_HOURS = 72
MAX_RANGE_DAYS = 31

SUPPORTED_LEAD_TIMES = list(range(24, 49, 2))
SUPPORTED_ACCURACY_LEAD_TIMES = list(range(12, 49, 2))
CACHED_LEAD_TIMES = sorted(
    set(SUPPORTED_LEAD_TIMES) | set(SUPPORTED_ACCURACY_LEAD_TIMES)
)
