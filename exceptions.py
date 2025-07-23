"""
Custom exception classes for Pinfairy Bot
Provides specific error types for better error handling and debugging
"""

class PinfairyException(Exception):
    """Base exception for all Pinfairy-related errors"""
    def __init__(self, message: str, error_code: str = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)

class PinterestAPIException(PinfairyException):
    """Raised when Pinterest API operations fail"""
    pass

class InvalidURLException(PinfairyException):
    """Raised when a Pinterest URL is invalid or malformed"""
    pass

class DeadLinkException(PinfairyException):
    """Raised when a Pinterest link is dead or inaccessible"""
    pass

class RateLimitException(PinfairyException):
    """Raised when user hits rate limits"""
    pass

class QuotaExceededException(PinfairyException):
    """Raised when user exceeds daily quota"""
    pass

class DatabaseException(PinfairyException):
    """Raised when database operations fail"""
    pass

class MediaProcessingException(PinfairyException):
    """Raised when media processing fails"""
    pass

class BrowserException(PinfairyException):
    """Raised when browser automation fails"""
    pass

class ConfigurationException(PinfairyException):
    """Raised when configuration is invalid or missing"""
    pass

class AuthenticationException(PinfairyException):
    """Raised when authentication fails"""
    pass