"""
Comprehensive Pinterest service tests
Tests Pinterest API integration, caching, error handling, and performance
"""

import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from services.pinterest import (
    PinterestService, CacheManager, ConnectionPool, 
    RetryMixin, BrowserManager, PinterestMedia
)
from exceptions import (
    PinterestAPIException, InvalidURLException, 
    DeadLinkException, NetworkException
)


class TestCacheManager:
    """Test cache manager functionality"""
    
    @pytest.fixture
    def cache_manager(self):
        """Create cache manager for testing"""
        return CacheManager()
    
    def test_cache_key_generation(self, cache_manager):
        """Test cache key generation"""
        url = "https://pinterest.com/test"
        params = {"param1": "value1"}
        
        key1 = cache_manager._generate_key(url, params)
        key2 = cache_manager._generate_key(url, params)
        key3 = cache_manager._generate_key(url, {"param1": "value2"})
        
        assert key1 == key2  # Same inputs should generate same key
        assert key1 != key3  # Different inputs should generate different keys
    
    def test_cache_set_and_get(self, cache_manager):
        """Test cache set and get operations"""
        url = "https://pinterest.com/test"
        data = {"title": "Test Pin", "url": "https://example.com/image.jpg"}
        
        # Set cache
        cache_manager.set(url, data)
        
        # Get cache
        cached_data = cache_manager.get(url, ttl=300)
        assert cached_data == data
    
    def test_cache_expiration(self, cache_manager):
        """Test cache expiration"""
        url = "https://pinterest.com/test"
        data = {"title": "Test Pin"}
        
        # Set cache with very short TTL
        cache_manager.set(url, data)
        
        # Should return None after expiration
        cached_data = cache_manager.get(url, ttl=0)  # Expired immediately
        assert cached_data is None
    
    def test_cache_size_management(self, cache_manager):
        """Test cache size management"""
        # Fill cache beyond max size
        for i in range(1100):  # More than max_cache_size (1000)
            cache_manager.set(f"https://pinterest.com/test{i}", {"data": i})
        
        # Cache should not exceed reasonable size
        assert len(cache_manager._cache) <= 1000


class TestConnectionPool:
    """Test HTTP connection pool"""
    
    @pytest.fixture
    async def connection_pool(self):
        """Create connection pool for testing"""
        pool = ConnectionPool(max_connections=3)
        yield pool
        await pool.close_all()
    
    @pytest.mark.asyncio
    async def test_get_and_return_client(self, connection_pool):
        """Test getting and returning HTTP clients"""
        # Get client
        client = await connection_pool.get_client()
        assert isinstance(client, httpx.AsyncClient)
        
        # Return client
        await connection_pool.return_client(client)
        assert len(connection_pool._clients) == 1
    
    @pytest.mark.asyncio
    async def test_client_reuse(self, connection_pool):
        """Test client reuse from pool"""
        # Get and return client
        client1 = await connection_pool.get_client()
        await connection_pool.return_client(client1)
        
        # Get client again (should reuse)
        client2 = await connection_pool.get_client()
        assert client1 is client2
        
        await connection_pool.return_client(client2)


class TestRetryMixin:
    """Test retry functionality with circuit breaker"""
    
    @pytest.fixture
    def retry_mixin(self):
        """Create retry mixin for testing"""
        return RetryMixin()
    
    @pytest.mark.asyncio
    async def test_successful_retry(self, retry_mixin):
        """Test successful operation without retry"""
        async def successful_operation():
            return "success"
        
        result = await retry_mixin.retry_with_backoff(
            successful_operation, max_retries=3
        )
        assert result == "success"
    
    @pytest.mark.asyncio
    async def test_retry_with_failure(self, retry_mixin):
        """Test retry mechanism with eventual success"""
        call_count = 0
        
        async def failing_then_success():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise httpx.ConnectTimeout("Connection timeout")
            return "success"
        
        result = await retry_mixin.retry_with_backoff(
            failing_then_success, max_retries=3, base_delay=0.01
        )
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_circuit_breaker(self, retry_mixin):
        """Test circuit breaker functionality"""
        async def always_failing():
            raise httpx.ConnectTimeout("Always fails")
        
        # Trigger circuit breaker
        for _ in range(5):
            try:
                await retry_mixin.retry_with_backoff(
                    always_failing, max_retries=1, base_delay=0.01
                )
            except:
                pass
        
        # Circuit should be open now
        with pytest.raises(PinterestAPIException, match="Circuit breaker open"):
            await retry_mixin.retry_with_backoff(
                always_failing, max_retries=1
            )


class TestPinterestService:
    """Test Pinterest service functionality"""
    
    @pytest.fixture
    async def pinterest_service(self):
        """Create Pinterest service for testing"""
        service = PinterestService()
        await service.initialize()
        yield service
        await service.close()
    
    @pytest.mark.asyncio
    async def test_service_initialization(self, pinterest_service):
        """Test service initialization"""
        assert pinterest_service._connection_pool is not None
        assert pinterest_service._cache_manager is not None
        assert pinterest_service._browser_manager is not None
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, pinterest_service):
        """Test rate limiting functionality"""
        endpoint = "https://pinterest.com/test"
        
        # First request should pass
        await pinterest_service._rate_limit_check(endpoint)
        
        # Second immediate request should be delayed
        start_time = asyncio.get_event_loop().time()
        await pinterest_service._rate_limit_check(endpoint)
        end_time = asyncio.get_event_loop().time()
        
        # Should have been delayed
        assert end_time - start_time >= 0.9  # Close to 1 second delay
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.request')
    async def test_make_request_success(self, mock_request, pinterest_service):
        """Test successful HTTP request"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_request.return_value = mock_response
        
        response = await pinterest_service._make_request("https://pinterest.com/test")
        assert response == mock_response
        mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.request')
    async def test_make_request_failure(self, mock_request, pinterest_service):
        """Test HTTP request failure"""
        # Mock failed response
        mock_request.side_effect = httpx.HTTPStatusError(
            "404 Not Found", request=MagicMock(), response=MagicMock()
        )
        
        with pytest.raises(httpx.HTTPStatusError):
            await pinterest_service._make_request("https://pinterest.com/test")
    
    @pytest.mark.asyncio
    async def test_caching_integration(self, pinterest_service):
        """Test caching integration"""
        cache_key = "test_key"
        test_data = {"title": "Test Pin", "url": "https://example.com/image.jpg"}
        
        # Set cached data
        await pinterest_service._set_cached_data(cache_key, test_data)
        
        # Get cached data
        cached_data = await pinterest_service._get_cached_data(cache_key)
        assert cached_data == test_data


class TestPinterestMedia:
    """Test Pinterest media data structure"""
    
    def test_pinterest_media_creation(self):
        """Test Pinterest media object creation"""
        media = PinterestMedia(
            url="https://pinterest.com/pin/123456789",
            media_type="photo",
            title="Test Pin",
            description="Test Description",
            media_url="https://i.pinimg.com/originals/test.jpg",
            resolution=(1920, 1080),
            quality="high"
        )
        
        assert media.url == "https://pinterest.com/pin/123456789"
        assert media.media_type == "photo"
        assert media.title == "Test Pin"
        assert media.resolution == (1920, 1080)
        assert media.quality == "high"
    
    def test_pinterest_media_defaults(self):
        """Test Pinterest media default values"""
        media = PinterestMedia(
            url="https://pinterest.com/pin/123456789",
            media_type="photo"
        )
        
        assert media.title == ""
        assert media.description == ""
        assert media.media_url == ""
        assert media.resolution == (0, 0)
        assert media.file_size == 0
        assert media.quality == "high"


class TestBrowserManager:
    """Test browser manager functionality"""
    
    @pytest.mark.asyncio
    @patch('playwright.async_api.async_playwright')
    async def test_browser_initialization(self, mock_playwright):
        """Test browser initialization"""
        # Mock playwright
        mock_playwright_instance = AsyncMock()
        mock_playwright.return_value.start.return_value = mock_playwright_instance
        mock_browser = AsyncMock()
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        
        browser_manager = BrowserManager()
        await browser_manager.initialize()
        
        assert browser_manager._initialized is True
        assert browser_manager._browser == mock_browser
    
    @pytest.mark.asyncio
    async def test_browser_singleton(self):
        """Test browser manager singleton pattern"""
        manager1 = BrowserManager()
        manager2 = BrowserManager()
        
        assert manager1 is manager2  # Should be same instance


class TestErrorHandling:
    """Test error handling in Pinterest service"""
    
    @pytest.mark.asyncio
    async def test_invalid_url_exception(self):
        """Test invalid URL exception handling"""
        with pytest.raises(InvalidURLException) as exc_info:
            raise InvalidURLException(
                "Invalid URL", 
                url="invalid-url"
            )
        
        assert "Invalid URL" in str(exc_info.value)
        assert exc_info.value.url == "invalid-url"
        assert exc_info.value.error_code == "E002"
    
    @pytest.mark.asyncio
    async def test_dead_link_exception(self):
        """Test dead link exception handling"""
        with pytest.raises(DeadLinkException) as exc_info:
            raise DeadLinkException("Dead link detected")
        
        assert "Dead link detected" in str(exc_info.value)
        assert exc_info.value.error_code == "E003"
    
    @pytest.mark.asyncio
    async def test_pinterest_api_exception(self):
        """Test Pinterest API exception handling"""
        with pytest.raises(PinterestAPIException) as exc_info:
            raise PinterestAPIException(
                "API error", 
                status_code=429
            )
        
        assert exc_info.value.status_code == 429
        assert exc_info.value.error_code == "E001"
        assert exc_info.value.retry_after == 60  # Rate limit retry


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
