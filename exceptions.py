"""
Enhanced custom exception classes for Pinfairy Bot
Provides specific error types for better error handling, debugging, and user feedback
"""

import time
import traceback
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class ErrorContext:
    """Context information for errors"""
    user_id: Optional[int] = None
    username: Optional[str] = None
    command: Optional[str] = None
    url: Optional[str] = None
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

class PinfairyException(Exception):
    """Enhanced base exception for all Pinfairy-related errors"""

    def __init__(self, message: str, error_code: str = None,
                 context: ErrorContext = None, user_message: str = None,
                 retry_after: int = None, should_log: bool = True):
        self.message = message
        self.error_code = error_code or "E000"
        self.context = context or ErrorContext()
        self.user_message = user_message or message
        self.retry_after = retry_after
        self.should_log = should_log
        self.traceback_str = traceback.format_exc()
        super().__init__(self.message)

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging"""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "user_message": self.user_message,
            "context": {
                "user_id": self.context.user_id,
                "username": self.context.username,
                "command": self.context.command,
                "url": self.context.url,
                "timestamp": self.context.timestamp
            },
            "retry_after": self.retry_after,
            "traceback": self.traceback_str
        }

    def get_user_message(self) -> str:
        """Get user-friendly error message"""
        if self.retry_after:
            return f"{self.user_message} Coba lagi dalam {self.retry_after} detik."
        return self.user_message

class PinterestAPIException(PinfairyException):
    """Raised when Pinterest API operations fail"""

    def __init__(self, message: str, status_code: int = None, **kwargs):
        self.status_code = status_code
        error_code = "E001"
        user_message = "❌ Terjadi kesalahan saat mengakses Pinterest. Silakan coba lagi."

        if status_code == 429:
            user_message = "⏳ Terlalu banyak permintaan. Tunggu sebentar dan coba lagi."
            kwargs['retry_after'] = 60
        elif status_code == 404:
            user_message = "❌ Konten Pinterest tidak ditemukan atau telah dihapus."

        super().__init__(message, error_code, user_message=user_message, **kwargs)

class InvalidURLException(PinfairyException):
    """Raised when a Pinterest URL is invalid or malformed"""

    def __init__(self, message: str, url: str = None, **kwargs):
        self.url = url
        error_code = "E002"
        user_message = "❌ URL Pinterest tidak valid. Pastikan URL benar dan coba lagi."

        if kwargs.get('context'):
            kwargs['context'].url = url

        super().__init__(message, error_code, user_message=user_message, **kwargs)

class DeadLinkException(PinfairyException):
    """Raised when a Pinterest link is dead or inaccessible"""

    def __init__(self, message: str, **kwargs):
        error_code = "E003"
        user_message = "❌ Link Pinterest sudah mati atau tidak dapat diakses."
        super().__init__(message, error_code, user_message=user_message, **kwargs)

class RateLimitException(PinfairyException):
    """Raised when user hits rate limits"""

    def __init__(self, message: str, remaining_time: int = None, **kwargs):
        self.remaining_time = remaining_time
        error_code = "E004"

        if remaining_time:
            user_message = f"⏳ Tunggu {remaining_time} detik sebelum request berikutnya."
            kwargs['retry_after'] = remaining_time
        else:
            user_message = "⏳ Terlalu banyak permintaan. Tunggu sebentar dan coba lagi."
            kwargs['retry_after'] = 30

        super().__init__(message, error_code, user_message=user_message, **kwargs)

class QuotaExceededException(PinfairyException):
    """Raised when user exceeds daily quota"""

    def __init__(self, message: str, remaining_quota: int = 0, reset_time: str = None, **kwargs):
        self.remaining_quota = remaining_quota
        self.reset_time = reset_time
        error_code = "E005"

        if reset_time:
            user_message = f"⚠️ Quota harian habis. Reset pada {reset_time}."
        else:
            user_message = f"⚠️ Quota harian habis. Sisa: {remaining_quota}"

        super().__init__(message, error_code, user_message=user_message, **kwargs)

class DatabaseException(PinfairyException):
    """Raised when database operations fail"""

    def __init__(self, message: str, operation: str = None, **kwargs):
        self.operation = operation
        error_code = "E006"
        user_message = "❌ Terjadi kesalahan database. Silakan coba lagi nanti."
        super().__init__(message, error_code, user_message=user_message, **kwargs)

class MediaProcessingException(PinfairyException):
    """Raised when media processing fails"""

    def __init__(self, message: str, media_type: str = None, **kwargs):
        self.media_type = media_type
        error_code = "E007"
        user_message = f"❌ Gagal memproses {media_type or 'media'}. Silakan coba lagi."
        super().__init__(message, error_code, user_message=user_message, **kwargs)

class BrowserException(PinfairyException):
    """Raised when browser automation fails"""

    def __init__(self, message: str, **kwargs):
        error_code = "E008"
        user_message = "❌ Terjadi kesalahan browser. Silakan coba lagi nanti."
        super().__init__(message, error_code, user_message=user_message, **kwargs)

class ConfigurationException(PinfairyException):
    """Raised when configuration is invalid or missing"""

    def __init__(self, message: str, config_key: str = None, **kwargs):
        self.config_key = config_key
        error_code = "E009"
        user_message = "❌ Konfigurasi bot bermasalah. Hubungi admin."
        super().__init__(message, error_code, user_message=user_message, **kwargs)

class AuthenticationException(PinfairyException):
    """Raised when authentication fails"""

    def __init__(self, message: str, **kwargs):
        error_code = "E010"
        user_message = "❌ Autentikasi gagal. Hubungi admin."
        super().__init__(message, error_code, user_message=user_message, **kwargs)

class NetworkException(PinfairyException):
    """Raised when network operations fail"""

    def __init__(self, message: str, **kwargs):
        error_code = "E011"
        user_message = "❌ Koneksi bermasalah. Periksa internet dan coba lagi."
        kwargs['retry_after'] = 30
        super().__init__(message, error_code, user_message=user_message, **kwargs)

class ValidationException(PinfairyException):
    """Raised when input validation fails"""

    def __init__(self, message: str, field: str = None, **kwargs):
        self.field = field
        error_code = "E012"
        user_message = f"❌ Input tidak valid{f' untuk {field}' if field else ''}."
        super().__init__(message, error_code, user_message=user_message, **kwargs)

class ErrorHandler:
    """Centralized error handling and logging"""

    def __init__(self, logger=None):
        self.logger = logger
        self.error_stats = {
            'total_errors': 0,
            'error_types': {},
            'last_error_time': None
        }

    def handle_exception(self, exception: Exception, context: ErrorContext = None) -> str:
        """Handle exception and return user-friendly message"""
        self.error_stats['total_errors'] += 1
        self.error_stats['last_error_time'] = time.time()

        # Convert to PinfairyException if needed
        if not isinstance(exception, PinfairyException):
            exception = self._convert_to_pinfairy_exception(exception, context)

        # Update error statistics
        error_type = type(exception).__name__
        self.error_stats['error_types'][error_type] = self.error_stats['error_types'].get(error_type, 0) + 1

        # Log error if needed
        if exception.should_log and self.logger:
            self.logger.error(f"Error handled: {exception.error_code} - {exception.message}",
                            extra=exception.to_dict())

        return exception.get_user_message()

    def _convert_to_pinfairy_exception(self, exception: Exception, context: ErrorContext = None) -> PinfairyException:
        """Convert generic exception to PinfairyException"""
        error_message = str(exception)

        # Map common exceptions
        if isinstance(exception, (ConnectionError, TimeoutError)):
            return NetworkException(error_message, context=context)
        elif isinstance(exception, ValueError):
            return ValidationException(error_message, context=context)
        elif isinstance(exception, FileNotFoundError):
            return MediaProcessingException(error_message, context=context)
        else:
            return PinfairyException(error_message, error_code="E999",
                                   user_message="❌ Terjadi kesalahan tidak terduga.",
                                   context=context)

    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics"""
        return self.error_stats.copy()

    def reset_stats(self):
        """Reset error statistics"""
        self.error_stats = {
            'total_errors': 0,
            'error_types': {},
            'last_error_time': None
        }

# Global error handler instance
error_handler = ErrorHandler()