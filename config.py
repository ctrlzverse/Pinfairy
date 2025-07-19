"""
Configuration file for Pinfairybot
Contains all configurable settings and constants
"""

import os

# Bot Configuration
BOT_PREFIX = os.getenv("BOT_PREFIX", "/")
if not BOT_PREFIX or BOT_PREFIX.strip() == "":
    BOT_PREFIX = "/"
BOT_PREFIX = BOT_PREFIX.strip()

DEFAULT_DAILY_QUOTA = 100
RATE_LIMIT_SECONDS = 3
MAX_BOARDS_PER_REQUEST = 5
MAX_QUERY_LENGTH = 100
MIN_QUERY_LENGTH = 2

# File and Directory Settings
DOWNLOADS_DIR = "downloads"
DB_FILE = "bot_stats.db"
SESSION_FILE = "bot_session"

# Performance Monitoring
PERFORMANCE_LOG_INTERVAL = 300  # 5 minutes
CLEANUP_INTERVAL = 3600  # 1 hour
MAX_FILE_AGE_HOURS = 1

# User Settings
DEFAULT_USER_SETTINGS = {
    "language": "id",
    "notifications": True,
    "download_quality": "high"
}

# Quality Settings
QUALITY_SETTINGS = {
    "high": {"resolution": "originals", "format": "jpg"},
    "medium": {"resolution": "736x", "format": "jpg"},
    "low": {"resolution": "236x", "format": "webp"}
}

# Language Settings
SUPPORTED_LANGUAGES = ["id", "en"]

# Error Messages
ERROR_MESSAGES = {
    "quota_exceeded": "⚠️ Quota harian Anda sudah habis. Sisa: {remaining}",
    "rate_limited": "⏳ Tunggu {remaining:.1f} detik sebelum request berikutnya.",
    "invalid_url": "❌ URL tidak valid atau bukan dari Pinterest.",
    "download_failed": "❌ Gagal mengunduh media.",
    "board_limit": "⚠️ Maksimal {max_boards} board per request.",
    "query_too_short": "⚠️ Query pencarian terlalu pendek. Minimal {min_length} karakter.",
    "query_too_long": "⚠️ Query pencarian terlalu panjang. Maksimal {max_length} karakter."
}

# Success Messages
SUCCESS_MESSAGES = {
    "download_complete": "✅ {media_type} berhasil diunduh!",
    "settings_updated": "✅ Pengaturan berhasil diperbarui!",
    "quota_reset": "✅ Quota harian telah direset!",
    "feedback_sent": "✅ Terima kasih! Pesan Anda telah diteruskan ke admin.",
    "backup_sent": "✅ Backup berhasil dikirim!"
}

# Admin settings
ADMIN_IDS = [int(admin_id) for admin_id in os.getenv("ADMIN_IDS", "").split(',') if admin_id.strip().isdigit()]

# Pinterest API Settings
PINTEREST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.5',
}

PINTEREST_DOMAINS = ['pinterest.com', 'pin.it', 'www.pinterest.com']
PINTEREST_API_ENDPOINT = "https://www.pinterest.com/resource/BoardFeedResource/get/"

# Logging Configuration
LOG_FORMAT = '%(asctime)s - [%(levelname)s] - %(message)s'
LOG_DATE_FORMAT = '%d-%b-%y %H:%M:%S'
