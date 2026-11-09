"""
Scraper Utilities

Helper functions for data validation, formatting, and async rate limiting.

Fungsi pembantu untuk validasi data, pemformatan, dan pembatasan laju async.
"""

import asyncio
import json
import os
import sqlite3
import time
from typing import Any, Callable, Dict, List, Optional, TypeVar

import httpx

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Tiny HTTP response cache (sqlite) — no external dependency
# Cache respons HTTP kecil berbasis sqlite, tanpa dependensi eksternal
# ---------------------------------------------------------------------------

_CACHE_PATH = os.environ.get(
    "CACHE_DB", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "cache.sqlite")
)


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_CACHE_PATH), exist_ok=True)
    conn = sqlite3.connect(_CACHE_PATH, timeout=10)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT, exp REAL)"
    )
    return conn


def cache_get(key: str) -> Optional[Any]:
    """Return cached JSON value if fresh, else None."""
    try:
        with _conn() as conn:
            row = conn.execute("SELECT v, exp FROM kv WHERE k=?", (key,)).fetchone()
        if not row:
            return None
        val, exp = row
        if exp and exp < time.time():
            return None
        return json.loads(val)
    except Exception:  # noqa: BLE001
        return None


def cache_set(key: str, value: Any, ttl: int = 900) -> None:
    """Store JSON value with TTL seconds."""
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO kv (k, v, exp) VALUES (?,?,?)",
                (key, json.dumps(value, default=str), time.time() + ttl),
            )
    except Exception:  # noqa: BLE001
        pass


def now() -> int:
    """Unix timestamp helper."""
    return int(time.time())


class CachedSession:
    """Minimal httpx wrapper with sqlite-backed GET caching.

    Pembungkus httpx minimal dengan cache GET berbasis sqlite.
    """

    def __init__(self, ttl: int = 900, **client_kwargs: Any):
        self.ttl = ttl
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=client_kwargs.pop("timeout", 30),
            **client_kwargs,
        )

    def get(self, url: str, **kwargs: Any) -> httpx.Response:
        key = "http:" + url + ":" + json.dumps(
            {k: str(v) for k, v in kwargs.items()}, sort_keys=True
        )
        hit = cache_get(key)
        if hit is not None:
            return httpx.Response(
                200, json=hit, request=httpx.Request("GET", url)
            )
        resp = self._client.get(url, **kwargs)
        if resp.status_code == 200:
            try:
                cache_set(key, resp.json(), self.ttl)
            except ValueError:
                pass
        return resp

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self._client.post(url, **kwargs)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CachedSession":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Luhn checksum validation
# Validasi checksum Luhn (hanya memeriksa digit kontrol, bukan pembuatan nomor)
# ---------------------------------------------------------------------------

def luhn_check(card_number: str) -> bool:
    """
    Validate a numeric string using the Luhn (mod-10) checksum algorithm.

    Memvalidasi string numerik memakai algoritma checksum Luhn (mod-10).
    Hanya memeriksa digit kontrol; tidak membuat atau menebak nomor.

    Args:
        card_number: Digits, spaces/dashes allowed / Digit, spasi/strip diperbolehkan

    Returns:
        bool: True if checksum valid / True jika checksum valid
    """
    if not isinstance(card_number, str):
        return False

    # Strip common separators, keep digits only
    # Buang pemisah umum, simpan digit saja
    digits = [c for c in card_number if c.isdigit()]
    if len(digits) < 12 or len(digits) > 19:
        return False

    total = 0
    # Iterate right-to-left, doubling every second digit
    # Iterasi kanan-ke-kiri, gandakan tiap digit kedua
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d

    return total % 10 == 0


# ---------------------------------------------------------------------------
# Region metadata
# Metadata wilayah (nama negara + emoji bendera)
# ---------------------------------------------------------------------------

_REGION_DATA: Dict[str, Dict[str, str]] = {
    "ID": {"country": "Indonesia",         "flag": "🇮🇩"},
    "MY": {"country": "Malaysia",          "flag": "🇲🇾"},
    "SG": {"country": "Singapore",         "flag": "🇸🇬"},
    "TH": {"country": "Thailand",          "flag": "🇹🇭"},
    "VN": {"country": "Vietnam",           "flag": "🇻🇳"},
    "PH": {"country": "Philippines",       "flag": "🇵🇭"},
    "US": {"country": "United States",     "flag": "🇺🇸"},
    "GB": {"country": "United Kingdom",    "flag": "🇬🇧"},
    "JP": {"country": "Japan",             "flag": "🇯🇵"},
    "KR": {"country": "South Korea",       "flag": "🇰🇷"},
    "CN": {"country": "China",             "flag": "🇨🇳"},
    "IN": {"country": "India",             "flag": "🇮🇳"},
    "BR": {"country": "Brazil",            "flag": "🇧🇷"},
    "MX": {"country": "Mexico",            "flag": "🇲🇽"},
    "DE": {"country": "Germany",           "flag": "🇩🇪"},
    "FR": {"country": "France",            "flag": "🇫🇷"},
    "AU": {"country": "Australia",         "flag": "🇦🇺"},
    "SA": {"country": "Saudi Arabia",      "flag": "🇸🇦"},
    "AE": {"country": "United Arab Emirates", "flag": "🇦🇪"},
    "TR": {"country": "Turkey",            "flag": "🇹🇷"},
}


def geo_flags(region: Optional[str] = None) -> Dict[str, Any]:
    """
    Return region code -> country name + flag emoji.

    Mengembalikan peta kode wilayah -> nama negara + emoji bendera.

    Args:
        region: Optional single region code (e.g. 'ID'). None returns all.
                Kode wilayah tunggal opsional. None mengembalikan semua.

    Returns:
        Dict: {code: {"country": str, "flag": str}} or a single entry.
              {kode: {...}} atau satu entri.
    """
    if region is None:
        return {code: dict(meta) for code, meta in _REGION_DATA.items()}

    code = str(region).strip().upper()
    meta = _REGION_DATA.get(code)
    if meta is None:
        return {code: {"country": "Unknown", "flag": "🏳️"}}
    return {code: dict(meta)}


# ---------------------------------------------------------------------------
# Duration formatting
# Pemformatan durasi
# ---------------------------------------------------------------------------

def parse_duration(seconds: Any) -> str:
    """
    Format seconds as 'M:SS' (or 'H:MM:SS' for one hour+).

    Memformat detik menjadi 'M:SS' (atau 'H:MM:SS' bila >= 1 jam).

    Args:
        seconds: Duration in seconds / Durasi dalam detik

    Returns:
        str: e.g. '0:25', '3:07', '1:02:09'
    """
    total = safe_int(seconds, default=0)
    if total < 0:
        total = 0

    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)

    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# ---------------------------------------------------------------------------
# Safe integer parsing
# Parsing integer yang aman
# ---------------------------------------------------------------------------

def safe_int(val: Any, default: int = 0) -> int:
    """
    Convert any value to int without raising.

    Mengubah nilai apa pun menjadi int tanpa melempar error.

    Handles: int, float, numeric strings ("12", "12.5", "1,234", "1.2K", "3M").
    Menangani: int, float, string numerik termasuk sufiks K/M.

    Args:
        val: Value to convert / Nilai yang dikonversi
        default: Fallback on failure / Nilai cadangan bila gagal

    Returns:
        int
    """
    if val is None:
        return default
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        try:
            return int(val)
        except (ValueError, OverflowError):
            return default

    try:
        text = str(val).strip().replace(",", "")
        if not text:
            return default

        # Handle shorthand suffixes: K (thousand), M (million), B (billion)
        # Tangani sufiks singkat: K, M, B
        multiplier = 1
        upper = text.upper()
        for suffix, mult in (("K", 1_000), ("M", 1_000_000), ("B", 1_000_000_000)):
            if upper.endswith(suffix):
                multiplier = mult
                text = text[:-1]
                break

        return int(float(text) * multiplier)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# List chunking
# Pemecahan list menjadi potongan
# ---------------------------------------------------------------------------

def chunk_list(lst: List[T], chunk_size: int) -> List[List[T]]:
    """
    Split a list into fixed-size chunks.

    Memecah list menjadi potongan berukuran tetap.

    Args:
        lst: Source list / List sumber
        chunk_size: Max items per chunk (must be > 0) / Ukuran maksimum per potongan

    Returns:
        List[List]: Chunks; empty input yields empty list.
                    Potongan; input kosong menghasilkan list kosong.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0 / chunk_size harus > 0")
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


# ---------------------------------------------------------------------------
# Async retry with exponential backoff
# Retry async dengan backoff eksponensial
# ---------------------------------------------------------------------------

async def retry_async(
    fn: Callable[..., Any],
    max_attempts: int = 3,
    delay: float = 2,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """
    Call an async function with retries and exponential backoff.

    Memanggil fungsi async dengan percobaan ulang dan backoff eksponensial.

    Delay sequence for delay=2: 2s, 4s, 8s, ...

    Args:
        fn: Coroutine function / Fungsi korutin
        max_attempts: Total attempts (>= 1) / Total percobaan
        delay: Base delay in seconds / Delay dasar dalam detik
        *args, **kwargs: Forwarded to fn / Diteruskan ke fn

    Returns:
        Any: fn result / Hasil fn

    Raises:
        Last exception if all attempts fail / Exception terakhir bila semua gagal
    """
    if max_attempts < 1:
        raise ValueError("max_attempts must be >= 1 / max_attempts harus >= 1")

    last_exc: Optional[BaseException] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 - caller decides on retry
            last_exc = exc
            if attempt == max_attempts:
                break
            await asyncio.sleep(delay * (2 ** (attempt - 1)))

    assert last_exc is not None
    raise last_exc


# ---------------------------------------------------------------------------
# Rate limiter (token bucket, per-second refill)
# Pembatas laju (token bucket, isi ulang per detik)
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Async token-bucket rate limiter.

    Pembatas laju async berbasis token bucket.

    Example / Contoh:
        limiter = RateLimiter(rate=5)   # 5 requests/sec
        await limiter.acquire()
    """

    def __init__(self, rate: float = 1.0, burst: Optional[int] = None):
        """
        Args:
            rate: Tokens refilled per second / Token diisi per detik
            burst: Max bucket capacity (default: ceil(rate)) / Kapasitas maksimum
        """
        if rate <= 0:
            raise ValueError("rate must be > 0 / rate harus > 0")

        self.rate = float(rate)
        self.capacity = float(burst if burst is not None else max(1, int(rate)))
        self._tokens = self.capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        """Add tokens proportional to elapsed time / Tambah token sesuai waktu berjalan."""
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed > 0:
            self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
            self._last_refill = now

    async def acquire(self, tokens: float = 1.0) -> None:
        """
        Wait until `tokens` are available, then consume them.

        Tunggu sampai `tokens` tersedia, lalu konsumsi.
        """
        if tokens <= 0:
            return
        if tokens > self.capacity:
            raise ValueError(
                "tokens exceeds bucket capacity / tokens melebihi kapasitas bucket"
            )

        async with self._lock:
            while True:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                # Sleep just long enough for the deficit to refill
                # Tidur selama kekurangan token terisi
                wait = (tokens - self._tokens) / self.rate
                await asyncio.sleep(max(wait, 0.001))

    @property
    def available(self) -> float:
        """Current token count / Jumlah token saat ini."""
        self._refill()
        return self._tokens