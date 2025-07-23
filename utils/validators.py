"""
Input validation utilities for Pinfairy Bot
Provides comprehensive validation for URLs, user inputs, and configuration
"""

import re
import httpx
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse, parse_qs
from constants import (
    PINTEREST_DOMAINS, MIN_QUERY_LENGTH, MAX_QUERY_LENGTH, 
    MAX_BOARDS_PER_REQUEST, URL_PATTERNS, SUPPORTED_LANGUAGES
)
from exceptions import InvalidURLException, DeadLinkException, ConfigurationException
from utils.logger import get_logger

logger = get_logger(__name__)

class URLValidator:
    """Validates Pinterest URLs and checks their accessibility"""
    
    @staticmethod
    def is_valid_url_format(url: str) -> bool:
        """Check if URL has valid format"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def is_pinterest_domain(url: str) -> bool:
        """Check if URL is from Pinterest domain"""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            return any(pinterest_domain in domain for pinterest_domain in PINTEREST_DOMAINS)
        except Exception:
            return False
    
    @staticmethod
    def extract_pinterest_urls(text: str) -> List[str]:
        """Extract all Pinterest URLs from text"""
        pattern = URL_PATTERNS["pinterest_url"]
        urls = re.findall(pattern, text, re.IGNORECASE)
        return [url[0] if isinstance(url, tuple) else url for url in urls]
    
    @staticmethod
    def clean_url(url: str) -> str:
        """Clean and normalize Pinterest URL"""
        url = url.strip().rstrip('`"\'')
        
        # Remove tracking parameters
        if '?' in url:
            base_url, params = url.split('?', 1)
            parsed_params = parse_qs(params)
            # Keep only essential parameters
            essential_params = {}
            for key, value in parsed_params.items():
                if key in ['pin', 'board']:
                    essential_params[key] = value
            
            if essential_params:
                param_string = '&'.join([f"{k}={v[0]}" for k, v in essential_params.items()])
                url = f"{base_url}?{param_string}"
            else:
                url = base_url
        
        return url
    
    @staticmethod
    async def check_url_accessibility(url: str, timeout: int = 10) -> Tuple[bool, Optional[str]]:
        """Check if URL is accessible"""
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                response = await client.head(url)
                if response.status_code == 200:
                    return True, None
                else:
                    return False, f"HTTP {response.status_code}"
        except httpx.TimeoutException:
            return False, "Request timeout"
        except httpx.RequestError as e:
            return False, f"Request error: {str(e)}"
        except Exception as e:
            return False, f"Unknown error: {str(e)}"
    
    @staticmethod
    def get_url_type(url: str) -> str:
        """Determine the type of Pinterest URL (pin, board, user, search)"""
        url_lower = url.lower()
        
        if '/pin/' in url_lower or 'pin.it' in url_lower:
            return 'pin'
        elif '/board/' in url_lower or ('/' in url_lower and url_lower.count('/') >= 4):
            return 'board'
        elif '/search/' in url_lower:
            return 'search'
        elif '/' in url_lower and url_lower.count('/') == 3:
            return 'user'
        else:
            return 'unknown'

class InputValidator:
    """Validates user inputs and commands"""
    
    @staticmethod
    def validate_search_query(query: str) -> Dict[str, Any]:
        """Validate search query"""
        if not query or not isinstance(query, str):
            return {
                "valid": False,
                "error": "Query tidak boleh kosong",
                "error_code": "EMPTY_QUERY"
            }
        
        query = query.strip()
        
        if len(query) < MIN_QUERY_LENGTH:
            return {
                "valid": False,
                "error": f"Query terlalu pendek. Minimal {MIN_QUERY_LENGTH} karakter",
                "error_code": "QUERY_TOO_SHORT"
            }
        
        if len(query) > MAX_QUERY_LENGTH:
            return {
                "valid": False,
                "error": f"Query terlalu panjang. Maksimal {MAX_QUERY_LENGTH} karakter",
                "error_code": "QUERY_TOO_LONG"
            }
        
        # Remove potentially harmful characters
        sanitized_query = re.sub(r'[<>"\';\\]', '', query)
        
        return {
            "valid": True,
            "query": sanitized_query,
            "original_query": query
        }
    
    @staticmethod
    def validate_board_urls(urls: List[str]) -> Dict[str, Any]:
        """Validate list of board URLs"""
        if not urls:
            return {
                "valid": False,
                "error": "Tidak ada URL yang diberikan",
                "error_code": "NO_URLS"
            }
        
        if len(urls) > MAX_BOARDS_PER_REQUEST:
            return {
                "valid": False,
                "error": f"Maksimal {MAX_BOARDS_PER_REQUEST} board per request",
                "error_code": "TOO_MANY_BOARDS"
            }
        
        valid_urls = []
        invalid_urls = []
        
        for url in urls:
            try:
                cleaned_url = URLValidator.clean_url(url)
                if URLValidator.is_valid_url_format(cleaned_url) and URLValidator.is_pinterest_domain(cleaned_url):
                    url_type = URLValidator.get_url_type(cleaned_url)
                    if url_type in ['board', 'user']:
                        valid_urls.append(cleaned_url)
                    else:
                        invalid_urls.append(url)
                else:
                    invalid_urls.append(url)
            except Exception:
                invalid_urls.append(url)
        
        return {
            "valid": len(valid_urls) > 0,
            "valid_urls": valid_urls,
            "invalid_urls": invalid_urls,
            "total_valid": len(valid_urls),
            "total_invalid": len(invalid_urls)
        }
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for safe file operations"""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = re.sub(r'[^\w\s\-_\.]', '', filename)
        filename = filename.strip()
        
        # Limit length
        if len(filename) > 100:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:95] + ('.' + ext if ext else '')
        
        return filename or 'untitled'
    
    @staticmethod
    def validate_user_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate user settings"""
        valid_settings = {}
        errors = []
        
        # Validate language
        if 'language' in settings:
            if settings['language'] in SUPPORTED_LANGUAGES:
                valid_settings['language'] = settings['language']
            else:
                errors.append(f"Invalid language: {settings['language']}")
        
        # Validate notifications
        if 'notifications' in settings:
            if isinstance(settings['notifications'], bool):
                valid_settings['notifications'] = settings['notifications']
            else:
                errors.append("Notifications must be boolean")
        
        # Validate download quality
        if 'download_quality' in settings:
            if settings['download_quality'] in ['high', 'medium', 'low']:
                valid_settings['download_quality'] = settings['download_quality']
            else:
                errors.append(f"Invalid quality: {settings['download_quality']}")
        
        # Validate auto_detect
        if 'auto_detect' in settings:
            if isinstance(settings['auto_detect'], bool):
                valid_settings['auto_detect'] = settings['auto_detect']
            else:
                errors.append("Auto detect must be boolean")
        
        return {
            "valid": len(errors) == 0,
            "settings": valid_settings,
            "errors": errors
        }

class ConfigValidator:
    """Validates configuration and environment variables"""
    
    @staticmethod
    def validate_environment() -> Dict[str, Any]:
        """Validate required environment variables"""
        import os
        from constants import REQUIRED_ENV_VARS, OPTIONAL_ENV_VARS
        
        missing_vars = []
        invalid_vars = []
        valid_config = {}
        
        # Check required variables
        for var in REQUIRED_ENV_VARS:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            else:
                valid_config[var] = value
        
        # Check optional variables with defaults
        for var, default in OPTIONAL_ENV_VARS.items():
            value = os.getenv(var, default)
            valid_config[var] = value
        
        # Validate specific formats
        if 'API_ID' in valid_config:
            try:
                valid_config['API_ID'] = int(valid_config['API_ID'])
            except ValueError:
                invalid_vars.append('API_ID must be integer')
        
        if 'ADMIN_IDS' in valid_config and valid_config['ADMIN_IDS']:
            try:
                admin_ids = [int(id.strip()) for id in valid_config['ADMIN_IDS'].split(',') if id.strip()]
                valid_config['ADMIN_IDS'] = admin_ids
            except ValueError:
                invalid_vars.append('ADMIN_IDS must be comma-separated integers')
        
        return {
            "valid": len(missing_vars) == 0 and len(invalid_vars) == 0,
            "config": valid_config,
            "missing_vars": missing_vars,
            "invalid_vars": invalid_vars
        }

# Convenience functions
async def validate_pinterest_url(url: str) -> Dict[str, Any]:
    """Comprehensive Pinterest URL validation"""
    try:
        # Basic format validation
        if not url or not isinstance(url, str):
            raise InvalidURLException("URL tidak valid", "INVALID_FORMAT")
        
        # Clean URL
        cleaned_url = URLValidator.clean_url(url)
        
        # Format validation
        if not URLValidator.is_valid_url_format(cleaned_url):
            raise InvalidURLException("Format URL tidak valid", "INVALID_FORMAT")
        
        # Domain validation
        if not URLValidator.is_pinterest_domain(cleaned_url):
            raise InvalidURLException("URL bukan dari Pinterest", "INVALID_DOMAIN")
        
        # Length validation
        if len(cleaned_url) > 2000:
            raise InvalidURLException("URL terlalu panjang", "URL_TOO_LONG")
        
        # Accessibility check
        is_accessible, error_msg = await URLValidator.check_url_accessibility(cleaned_url)
        if not is_accessible:
            raise DeadLinkException(f"Link tidak dapat diakses: {error_msg}", "DEAD_LINK")
        
        # Get URL type
        url_type = URLValidator.get_url_type(cleaned_url)
        
        return {
            "is_valid": True,
            "url": cleaned_url,
            "original_url": url,
            "url_type": url_type,
            "is_dead": False
        }
        
    except (InvalidURLException, DeadLinkException) as e:
        logger.error(f"URL validation failed: {e.message}", error_code=e.error_code, url=url)
        return {
            "is_valid": False,
            "url": url,
            "message": e.message,
            "error_code": e.error_code,
            "is_dead": isinstance(e, DeadLinkException)
        }
    except Exception as e:
        logger.error(f"Unexpected error in URL validation: {str(e)}", exc_info=True, url=url)
        return {
            "is_valid": False,
            "url": url,
            "message": "Terjadi kesalahan saat validasi URL",
            "error_code": "VALIDATION_ERROR",
            "is_dead": False
        }