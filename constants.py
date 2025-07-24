"""
Constants and configuration values for Pinfairy Bot
Centralized location for all constant values used throughout the application
"""

import os
from typing import Dict, List

# Bot Configuration
DEFAULT_BOT_PREFIX = "/"
DEFAULT_DAILY_QUOTA = 100
DEFAULT_RATE_LIMIT_SECONDS = 3
MAX_BOARDS_PER_REQUEST = 5
MAX_QUERY_LENGTH = 100
MIN_QUERY_LENGTH = 2

# File and Directory Settings
DOWNLOADS_DIR = "downloads"
DB_FILE = "bot_stats.db"
SESSION_FILE = "bot_session"
BACKUP_DIR = "backups"
LOGS_DIR = "logs"

# Performance and Monitoring
PERFORMANCE_LOG_INTERVAL = 300  # 5 minutes
CLEANUP_INTERVAL = 3600  # 1 hour
MAX_FILE_AGE_HOURS = 1
MAX_RETRY_ATTEMPTS = 3
RETRY_DELAY_BASE = 1  # Base delay for exponential backoff
CONNECTION_TIMEOUT = 30
READ_TIMEOUT = 60

# Pinterest API Configuration
PINTEREST_DOMAINS = ['pinterest.com', 'pin.it', 'www.pinterest.com', 'id.pinterest.com']
PINTEREST_API_ENDPOINT = "https://www.pinterest.com/resource/BoardFeedResource/get/"
PINTEREST_SEARCH_ENDPOINT = "https://www.pinterest.com/search/pins/"

# HTTP Headers
PINTEREST_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0'
}

# Quality Settings
QUALITY_SETTINGS = {
    "high": {"resolution": "originals", "format": "jpg", "min_resolution": 500},
    "medium": {"resolution": "736x", "format": "jpg", "min_resolution": 300},
    "low": {"resolution": "236x", "format": "webp", "min_resolution": 200}
}

# User Settings
DEFAULT_USER_SETTINGS = {
    "language": "id",
    "notifications": True,
    "download_quality": "high",
    "auto_detect": True,
    "compress_albums": False
}

# Language Settings
SUPPORTED_LANGUAGES = ["id", "en"]

# Database Schema
DB_SCHEMA_VERSION = "1.0.0"

# Error Codes
ERROR_CODES = {
    "INVALID_URL": "E001",
    "DEAD_LINK": "E002",
    "RATE_LIMITED": "E003",
    "QUOTA_EXCEEDED": "E004",
    "DOWNLOAD_FAILED": "E005",
    "BOARD_LIMIT_EXCEEDED": "E006",
    "QUERY_TOO_SHORT": "E007",
    "QUERY_TOO_LONG": "E008",
    "DATABASE_ERROR": "E009",
    "BROWSER_ERROR": "E010",
    "CONFIG_ERROR": "E011",
    "AUTH_ERROR": "E012"
}

# Success Codes
SUCCESS_CODES = {
    "DOWNLOAD_COMPLETE": "S001",
    "SETTINGS_UPDATED": "S002",
    "QUOTA_RESET": "S003",
    "FEEDBACK_SENT": "S004",
    "BACKUP_CREATED": "S005"
}

# Message Templates
ERROR_MESSAGES = {
    "quota_exceeded": "⚠️ Quota harian Anda sudah habis. Sisa: {remaining}",
    "rate_limited": "⏳ Tunggu {remaining:.1f} detik sebelum request berikutnya.",
    "invalid_url": "❌ URL tidak valid atau bukan dari Pinterest.",
    "dead_link": "❌ Link sudah mati atau tidak dapat diakses.",
    "download_failed": "❌ Gagal mengunduh media.",
    "board_limit": "⚠️ Maksimal {max_boards} board per request.",
    "query_too_short": "⚠️ Query pencarian terlalu pendek. Minimal {min_length} karakter.",
    "query_too_long": "⚠️ Query pencarian terlalu panjang. Maksimal {max_length} karakter.",
    "database_error": "❌ Terjadi kesalahan database.",
    "browser_error": "❌ Terjadi kesalahan browser automation.",
    "config_error": "❌ Konfigurasi tidak valid.",
    "auth_error": "❌ Autentikasi gagal."
}

SUCCESS_MESSAGES = {
    "download_complete": "✅ {media_type} berhasil diunduh!",
    "settings_updated": "✅ Pengaturan berhasil diperbarui!",
    "quota_reset": "✅ Quota harian telah direset!",
    "feedback_sent": "✅ Terima kasih! Pesan Anda telah diteruskan ke admin.",
    "backup_sent": "✅ Backup berhasil dikirim!"
}

# Logging Configuration
LOG_FORMAT = '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Enhanced Cache Configuration
CACHE_TTL = {
    "user_settings": 300,        # 5 minutes
    "stats": 60,                 # 1 minute
    "pinterest_data": 1800,      # 30 minutes
    "board_data": 3600,          # 1 hour
    "url_validation": 7200,      # 2 hours
    "media_metadata": 3600,      # 1 hour
    "rate_limit": 60,            # 1 minute
    "quota_check": 300,          # 5 minutes
    "system_stats": 120,         # 2 minutes
    "user_profile": 300,         # 5 minutes
    "search_results": 900        # 15 minutes
}

# Database optimization settings
DB_OPTIMIZATION = {
    "connection_pool_size": 10,
    "max_connections": 20,
    "query_timeout": 30,
    "slow_query_threshold": 1.0,  # seconds
    "cache_size": 10000,
    "page_size": 4096,
    "journal_mode": "WAL",
    "synchronous": "NORMAL"
}

# Performance monitoring settings
PERFORMANCE_MONITORING = {
    "enable_metrics": True,
    "metrics_interval": 60,           # seconds
    "slow_operation_threshold": 2.0,  # seconds
    "memory_warning_threshold": 500,  # MB
    "cpu_warning_threshold": 80,      # percentage
    "disk_warning_threshold": 90      # percentage
}

# Regex Patterns
URL_PATTERNS = {
    "pinterest_url": r'https?://(www\.)?(id\.)?pinterest\.com/[^\s]+|https?://pin\.it/[^\s]+',
    "pinterest_image": r'https://i\.pinimg\.com/[^\s"\']+',
    "board_id": r'"board_id":\s*"(\d+)"',
    "bookmark": r'"bookmarks":\s*\["([^\"]+)"\]',
    "image_resolution": r'/(\d+)x(\d+)/'
}

# Admin Configuration
ADMIN_COMMANDS = [
    "backup", "restore", "stats_admin", "user_admin", 
    "broadcast", "maintenance", "logs"
]

# Feature Flags
FEATURES = {
    "auto_detect": True,
    "board_download": True,
    "video_download": True,
    "search_functionality": True,
    "user_profiles": True,
    "leaderboard": True,
    "feedback_system": True,
    "admin_panel": True,
    "performance_monitoring": True,
    "rate_limiting": True,
    "quota_system": True
}

# Browser Configuration
BROWSER_CONFIG = {
    "headless": True,
    "timeout": 60000,
    "viewport": {"width": 1920, "height": 1080},
    "user_agent": PINTEREST_HEADERS["User-Agent"]
}

# Media Processing
IMAGE_FORMATS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
VIDEO_FORMATS = ['.mp4', '.webm', '.mov']
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
MIN_IMAGE_RESOLUTION = 200 * 200

# Pagination
DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100
DEFAULT_BOARD_PAGE_SIZE = 50

# Environment Variables
REQUIRED_ENV_VARS = [
    "API_ID", "API_HASH", "BOT_TOKEN"
]

OPTIONAL_ENV_VARS = {
    "BOT_PREFIX": DEFAULT_BOT_PREFIX,
    "ADMIN_IDS": "",
    "FORCE_SUB_CHANNEL": "@aes_hub",
    "BROWSERLESS_TOKEN": "",
    "DATABASE_URL": "",
    "REDIS_URL": "",
    "LOG_LEVEL": "INFO"
}