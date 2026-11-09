"""Central configuration — all tunables and env-backed secrets in one place."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / "backend"
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = os.environ.get("DB_PATH", str(DATA_DIR / "cache.sqlite"))

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

CC_BASE = "https://ads.tiktok.com/creative_radar_api/v1"
CC_HEADERS = {
    "Accept": "application/json",
    "anonymous-user-id": "fake-user-id",
    "Content-Type": "application/json",
    "User-Agent": UA,
    "Referer": "https://ads.tiktok.com/business/creativecenter/inspiration/topads/pc/en",
}

FM_BASE = os.environ.get("FM_BASE", "https://openapi.fastmoss.com")
FM_KEY = os.environ.get("FM_API_KEY", "")

TT_RESEARCH = "https://open.tiktokapis.com/v2/research"
TT_TOKEN = os.environ.get("TT_RESEARCH_TOKEN", "")

# TikTok Shop Partner Center (official, requires app approval)
TTS_APP_KEY = os.environ.get("TTS_APP_KEY", "")
TTS_APP_SECRET = os.environ.get("TTS_APP_SECRET", "")
TTS_BASE = os.environ.get("TTS_BASE", "https://open-api.tiktokglobalshop.com")
TTS_SHOP_CIPHER = os.environ.get("TTS_SHOP_CIPHER", "")

CACHE_TTL_SECONDS = int(os.environ.get("CACHE_TTL_SECONDS", "900"))

# analytics assumptions (documented, tweakable)
ENGAGEMENT_RATE = float(os.environ.get("ENGAGEMENT_RATE", "0.045"))
CONVERSION_RATE = float(os.environ.get("CONVERSION_RATE", "0.018"))