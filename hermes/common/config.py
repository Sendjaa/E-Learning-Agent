"""Konfigurasi terpusat: env var, path, dan konstanta yang bisa disetel.

Semua nilai diambil dari file .env di root proyek.
"""

import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _env(key, default=""):
    val = os.getenv(key, default)
    return val.strip().strip('"').strip("'") if val else default


def _env_int(key, default):
    try:
        return int(_env(key, str(default)))
    except ValueError:
        return default


# --- LLM ---
LLM_PROVIDER = _env("LLM_PROVIDER", "openrouter").lower()

if LLM_PROVIDER == "deepinfra":
    LLM_API_KEY = _env("HERMES_API_KEY") or _env("DEEPINFRA_API_KEY")
    LLM_MODEL = _env("HERMES_MODEL") or _env("LLM_MODEL", "deepseek-ai/DeepSeek-V3.2-Exp")
    LLM_BASE_URL = _env("HERMES_BASE_URL") or _env("LLM_BASE_URL", "https://api.deepinfra.com/v1/openai")
    _llm_headers = None
else:
    LLM_API_KEY = _env("OPENROUTER_API_KEY") or _env("HERMES_API_KEY")
    LLM_MODEL = _env("LLM_MODEL") or _env("HERMES_MODEL", "google/gemini-2.5-flash:free")
    LLM_BASE_URL = _env("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    _llm_headers = {
        "HTTP-Referer": _env("OPENROUTER_REFERER", "https://github.com/assistant-hermes"),
        "X-Title": "Hermes E-Learning Agent",
    }

LLM_HEADERS = _llm_headers

# --- Telegram ---
TELEGRAM_BOT_TOKEN = _env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = _env("TELEGRAM_CHAT_ID")

# --- E-Learning Moodle ---
ELEARNING_URL = _env("ELEARNING_URL").rstrip("/")
ELEARNING_USERNAME = _env("ELEARNING_USERNAME")
ELEARNING_PASSWORD = _env("PASSWORD")

# --- Database ---
DB_PATH = _env("HERMES_DB", os.path.join(BASE_DIR, "hermes.db"))

# --- Roster ---
# Daftar kursi ada di hermes/roster.py — lima kursi, satu per jenis kerja.
# Tidak ada mode: kursi yang tidak kebagian tugas tampil kosong di dashboard.

# Kursi PM memeriksa tiap draf yang selesai dikerjakan kursi lain.
# Menghabiskan satu panggilan LLM tambahan per draf, jadi bisa dimatikan.
PM_REVIEW = _env("PM_REVIEW", "1").lower() not in ("0", "false", "no")

# --- Loop & interval ---
# Jeda antar pengecekan linimasa (detik). Default 2 jam seperti versi lama.
CHECK_INTERVAL = _env_int("CHECK_INTERVAL", 7200)
# Jeda polling worker antrian jawaban (detik).
WORKER_INTERVAL = _env_int("WORKER_INTERVAL", 10)

# --- Dashboard ---
DASHBOARD_HOST = _env("DASHBOARD_HOST", "127.0.0.1")
DASHBOARD_PORT = _env_int("DASHBOARD_PORT", 8080)

# --- Bobot beban tugas ---
# Ambang sisa waktu (jam) untuk menentukan bobot urgensi sebuah tugas.
URGENT_HOURS = _env_int("URGENT_HOURS", 24)
SOON_HOURS = _env_int("SOON_HOURS", 72)
# Bobot dipakai saat menghitung skor beban tiap agent.
WEIGHT_URGENT = _env_int("WEIGHT_URGENT", 3)
WEIGHT_SOON = _env_int("WEIGHT_SOON", 2)
WEIGHT_NORMAL = _env_int("WEIGHT_NORMAL", 1)
