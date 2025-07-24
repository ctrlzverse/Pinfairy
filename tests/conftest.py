"""
Pytest configuration and fixtures for Pinfairy Bot tests
Provides common fixtures and test utilities
"""

import pytest
import asyncio
import tempfile
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_database():
    """Create temporary database for testing"""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    yield db_path
    
    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def mock_telegram_event():
    """Create mock Telegram event"""
    event = MagicMock()
    event.sender_id = 12345
    event.sender.username = "test_user"
    event.sender.first_name = "Test"
    event.sender.last_name = "User"
    event.text = "/test"
    event.reply = AsyncMock()
    event.edit = AsyncMock()
    event.pattern_match = MagicMock()
    event.pattern_match.group.return_value = "https://pinterest.com/pin/123456789"
    return event


@pytest.fixture
def mock_pinterest_response():
    """Create mock Pinterest API response"""
    return {
        "resource_response": {
            "data": {
                "id": "123456789",
                "title": "Test Pin",
                "description": "Test Description",
                "images": {
                    "orig": {
                        "url": "https://i.pinimg.com/originals/test.jpg",
                        "width": 1920,
                        "height": 1080
                    }
                },
                "videos": {
                    "video_list": {
                        "V_720P": {
                            "url": "https://v.pinimg.com/videos/test.mp4",
                            "width": 1280,
                            "height": 720
                        }
                    }
                }
            }
        }
    }


@pytest.fixture
def mock_database_service():
    """Create mock database service"""
    service = AsyncMock()
    service.initialize = AsyncMock()
    service.close = AsyncMock()
    service.create_user = AsyncMock(return_value=True)
    service.get_user_profile = AsyncMock(return_value={
        "user_id": 12345,
        "username": "test_user",
        "first_name": "Test",
        "last_name": "User",
        "daily_quota": 50,
        "downloads_today": 5,
        "total_downloads": 100,
        "is_banned": False
    })
    service.update_user_activity = AsyncMock()
    service.log_download = AsyncMock()
    service.check_rate_limit = AsyncMock(return_value={"allowed": True})
    service.check_user_quota = AsyncMock(return_value={"allowed": True, "remaining": 45})
    return service


@pytest.fixture
def mock_pinterest_service():
    """Create mock Pinterest service"""
    service = AsyncMock()
    service.initialize = AsyncMock()
    service.close = AsyncMock()
    service.get_pin_data = AsyncMock(return_value={
        "title": "Test Pin",
        "description": "Test Description",
        "media_url": "https://i.pinimg.com/originals/test.jpg",
        "media_type": "photo",
        "resolution": (1920, 1080)
    })
    service.download_media = AsyncMock(return_value="test_image.jpg")
    service.validate_url = AsyncMock(return_value={"is_valid": True})
    return service


@pytest.fixture
def mock_config():
    """Create mock configuration"""
    config = MagicMock()
    config.api_id = 12345
    config.api_hash = "test_hash"
    config.bot_token = "test_token"
    config.bot_prefix = "/"
    config.admin_users = [12345]
    config.max_daily_quota = 50
    config.rate_limit_window = 60
    config.rate_limit_max_requests = 10
    return config


@pytest.fixture
def mock_telethon_client():
    """Create mock Telethon client"""
    client = AsyncMock()
    client.start = AsyncMock()
    client.disconnect = AsyncMock()
    client.is_connected = MagicMock(return_value=True)
    client.add_event_handler = MagicMock()
    client.run_until_disconnected = AsyncMock()
    return client


@pytest.fixture
def mock_httpx_client():
    """Create mock HTTPX client"""
    client = AsyncMock()
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {"status": "success"}
    response.content = b"test content"
    response.raise_for_status.return_value = None
    client.get.return_value = response
    client.post.return_value = response
    client.request.return_value = response
    return client


@pytest.fixture
def mock_playwright_browser():
    """Create mock Playwright browser"""
    browser = AsyncMock()
    page = AsyncMock()
    page.goto = AsyncMock()
    page.content = AsyncMock(return_value="<html>Test content</html>")
    page.evaluate = AsyncMock(return_value="test result")
    page.close = AsyncMock()
    browser.new_page.return_value = page
    browser.close = AsyncMock()
    return browser


@pytest.fixture(autouse=True)
def mock_environment_variables():
    """Mock environment variables for testing"""
    env_vars = {
        "API_ID": "12345",
        "API_HASH": "test_hash",
        "BOT_TOKEN": "test_token",
        "BOT_PREFIX": "/",
        "DB_FILE": ":memory:",
        "LOG_LEVEL": "DEBUG"
    }
    
    with patch.dict(os.environ, env_vars):
        yield


@pytest.fixture
def mock_logger():
    """Create mock logger"""
    logger = MagicMock()
    logger.info = MagicMock()
    logger.warning = MagicMock()
    logger.error = MagicMock()
    logger.debug = MagicMock()
    logger.critical = MagicMock()
    return logger


class AsyncContextManagerMock:
    """Mock async context manager"""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
    
    async def __aenter__(self):
        return self.return_value
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def async_context_manager():
    """Create async context manager mock"""
    return AsyncContextManagerMock


# Performance testing utilities
@pytest.fixture
def performance_monitor():
    """Performance monitoring fixture"""
    import time
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.measurements = []
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
            if self.start_time:
                duration = self.end_time - self.start_time
                self.measurements.append(duration)
                return duration
            return 0
        
        def get_average(self):
            if self.measurements:
                return sum(self.measurements) / len(self.measurements)
            return 0
        
        def get_total(self):
            return sum(self.measurements)
        
        def reset(self):
            self.measurements.clear()
            self.start_time = None
            self.end_time = None
    
    return PerformanceMonitor()


# Test data generators
@pytest.fixture
def pinterest_urls():
    """Generate test Pinterest URLs"""
    return [
        "https://pinterest.com/pin/123456789/",
        "https://www.pinterest.com/pin/987654321/",
        "https://id.pinterest.com/pin/555666777/",
        "https://pin.it/abcd1234",
        "https://pinterest.com/username/boardname/",
        "https://www.pinterest.com/username/boardname/pin123/"
    ]


@pytest.fixture
def invalid_urls():
    """Generate invalid URLs for testing"""
    return [
        "https://google.com/search?q=test",
        "https://instagram.com/post/123",
        "not-a-url",
        "",
        None,
        "https://pinterest.com",  # Missing pin ID
        "https://pinterest.com/pin/",  # Empty pin ID
    ]


# Cleanup utilities
@pytest.fixture(autouse=True)
def cleanup_temp_files():
    """Cleanup temporary files after tests"""
    temp_files = []
    
    def register_temp_file(filepath):
        temp_files.append(filepath)
    
    yield register_temp_file
    
    # Cleanup
    for filepath in temp_files:
        try:
            if os.path.exists(filepath):
                os.unlink(filepath)
        except Exception:
            pass  # Ignore cleanup errors


# Test markers
def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
