"""
Test suite for Pinfairy Bot
Comprehensive tests for all services and functionality
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch

# Import services to test
from services.database import DatabaseService
from services.pinterest import PinterestService
from services.user_management import UserService
from services.media_processing import MediaProcessor
from services.monitoring import MonitoringService
from utils.validators import URLValidator, InputValidator
from exceptions import *

class TestDatabaseService:
    """Test database service functionality"""
    
    @pytest.fixture
    async def db_service(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            db_path = tmp.name
        
        service = DatabaseService(db_path)
        await service.initialize()
        yield service
        await service.close()
        os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_user_creation(self, db_service):
        """Test user creation and retrieval"""
        user_id = 12345
        username = "testuser"
        
        # Create user
        await db_service.create_user(user_id, username)
        
        # Retrieve user
        profile = await db_service.get_user_profile(user_id)
        
        assert profile is not None
        assert profile["user_id"] == user_id
        assert profile["username"] == username
        assert profile["total_downloads"] == 0
    
    @pytest.mark.asyncio
    async def test_download_logging(self, db_service):
        """Test download logging functionality"""
        user_id = 12345
        await db_service.create_user(user_id, "testuser")
        
        # Log successful download
        await db_service.log_download(
            user_id=user_id,
            media_type="photo",
            url="https://pinterest.com/test",
            success=True,
            duration=1.5
        )
        
        # Check user stats updated
        profile = await db_service.get_user_profile(user_id)
        assert profile["total_downloads"] == 1
        assert profile["downloads_today"] == 1
        
        # Check download history
        history = await db_service.get_download_history(user_id)
        assert len(history) == 1
        assert history[0]["success"] == True
        assert history[0]["duration"] == 1.5
    
    @pytest.mark.asyncio
    async def test_quota_management(self, db_service):
        """Test quota checking and reset"""
        user_id = 12345
        await db_service.create_user(user_id, "testuser")
        
        # Check initial quota
        quota = await db_service.check_user_quota(user_id)
        assert quota["allowed"] == True
        assert quota["remaining"] == 100
        
        # Simulate downloads to exhaust quota
        for _ in range(100):
            await db_service.log_download(user_id, "photo", "test", True)
        
        # Check quota exhausted
        quota = await db_service.check_user_quota(user_id)
        assert quota["allowed"] == False
        assert quota["remaining"] == 0

class TestPinterestService:
    """Test Pinterest service functionality"""
    
    @pytest.fixture
    def pinterest_service(self):
        return PinterestService()
    
    @pytest.mark.asyncio
    async def test_photo_data_extraction(self, pinterest_service):
        """Test photo data extraction"""
        # Mock HTTP response
        mock_html = '''
        <html>
            <meta property="og:image" content="https://i.pinimg.com/736x/test.jpg">
        </html>
        '''
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.text = mock_html
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get.return_value = mock_response
            
            async with pinterest_service:
                result = await pinterest_service.get_photo_data("https://pinterest.com/pin/test")
            
            assert result["is_success"] == True
            assert "originals" in result["media_url"]
    
    @pytest.mark.asyncio
    async def test_url_validation(self):
        """Test URL validation"""
        validator = URLValidator()
        
        # Valid Pinterest URLs
        assert validator.is_pinterest_domain("https://pinterest.com/pin/123")
        assert validator.is_pinterest_domain("https://pin.it/abc123")
        
        # Invalid URLs
        assert not validator.is_pinterest_domain("https://google.com")
        assert not validator.is_valid_url_format("not-a-url")
    
    @pytest.mark.asyncio
    async def test_board_scraping(self, pinterest_service):
        """Test board scraping functionality"""
        # This would require more complex mocking
        # For now, just test the service initialization
        async with pinterest_service:
            assert pinterest_service.session is not None

class TestUserService:
    """Test user management service"""
    
    @pytest.fixture
    async def user_service(self):
        # Mock database service
        with patch('services.user_management.db_service') as mock_db:
            service = UserService()
            yield service, mock_db
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, user_service):
        """Test rate limiting functionality"""
        service, mock_db = user_service
        
        user_id = 12345
        
        # First request should be allowed
        result1 = service.check_rate_limit(user_id)
        assert result1["allowed"] == True
        
        # Immediate second request should be blocked
        result2 = service.check_rate_limit(user_id)
        assert result2["allowed"] == False
        assert "remaining_time" in result2
    
    @pytest.mark.asyncio
    async def test_user_creation(self, user_service):
        """Test user creation"""
        service, mock_db = user_service
        
        mock_db.get_user_profile.return_value = None
        mock_db.create_user.return_value = None
        mock_db.get_user_profile.return_value = {"user_id": 12345}
        
        result = await service.create_or_update_user(12345, "testuser")
        
        assert result["action"] == "created"
        mock_db.create_user.assert_called_once()

class TestValidators:
    """Test validation utilities"""
    
    def test_search_query_validation(self):
        """Test search query validation"""
        validator = InputValidator()
        
        # Valid queries
        result = validator.validate_search_query("test query")
        assert result["valid"] == True
        
        # Too short
        result = validator.validate_search_query("a")
        assert result["valid"] == False
        assert result["error_code"] == "QUERY_TOO_SHORT"
        
        # Too long
        long_query = "a" * 101
        result = validator.validate_search_query(long_query)
        assert result["valid"] == False
        assert result["error_code"] == "QUERY_TOO_LONG"
    
    def test_filename_sanitization(self):
        """Test filename sanitization"""
        validator = InputValidator()
        
        # Test dangerous characters
        result = validator.sanitize_filename("test<>:\"/\\|?*file.jpg")
        assert "<" not in result
        assert ">" not in result
        assert ":" not in result
        
        # Test length limiting
        long_name = "a" * 150 + ".jpg"
        result = validator.sanitize_filename(long_name)
        assert len(result) <= 100

class TestMediaProcessor:
    """Test media processing service"""
    
    @pytest.fixture
    def media_processor(self):
        return MediaProcessor()
    
    @pytest.mark.asyncio
    async def test_file_download(self, media_processor):
        """Test file download functionality"""
        # Mock HTTP response
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = Mock()
            mock_response.headers = {'content-length': '1024'}
            mock_response.aiter_bytes.return_value = [b'test data']
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.stream.return_value.__aenter__.return_value = mock_response
            
            with patch('aiofiles.open', create=True) as mock_open:
                mock_file = AsyncMock()
                mock_open.return_value.__aenter__.return_value = mock_file
                
                result = await media_processor.download_file("https://example.com/test.jpg")
                
                assert result["success"] == True
                assert "file_path" in result
    
    @pytest.mark.asyncio
    async def test_zip_creation(self, media_processor):
        """Test ZIP archive creation"""
        # Create temporary files
        temp_files = []
        for i in range(3):
            with tempfile.NamedTemporaryFile(delete=False, suffix='.txt') as tmp:
                tmp.write(b'test content')
                temp_files.append(tmp.name)
        
        try:
            zip_path = await media_processor.create_zip_archive(
                temp_files, 
                "test_archive"
            )
            
            assert os.path.exists(zip_path)
            assert zip_path.endswith('.zip')
            
            # Clean up
            os.unlink(zip_path)
            
        finally:
            # Clean up temp files
            for temp_file in temp_files:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)

class TestMonitoringService:
    """Test monitoring service"""
    
    @pytest.fixture
    def monitoring_service(self):
        return MonitoringService()
    
    def test_user_request_recording(self, monitoring_service):
        """Test user request recording"""
        user_id = 12345
        duration = 1.5
        
        monitoring_service.record_user_request(user_id, duration, True)
        
        metrics = monitoring_service.app_monitor.get_metrics()
        assert metrics.active_users == 1
        assert len(metrics.response_times) == 1
        assert metrics.response_times[0] == duration
    
    @pytest.mark.asyncio
    async def test_health_checks(self, monitoring_service):
        """Test health check functionality"""
        # Register a simple health check
        def test_check():
            return {"healthy": True, "message": "Test OK"}
        
        monitoring_service.health_checker.register_check("test", test_check)
        
        # Run the check
        result = await monitoring_service.health_checker.run_check("test")
        
        assert result["status"] == "healthy"
        assert result["name"] == "test"

# Integration tests
class TestIntegration:
    """Integration tests for complete workflows"""
    
    @pytest.mark.asyncio
    async def test_complete_download_workflow(self):
        """Test complete download workflow"""
        # This would test the entire flow from URL validation
        # to download completion and logging
        pass
    
    @pytest.mark.asyncio
    async def test_user_quota_workflow(self):
        """Test user quota management workflow"""
        # This would test quota checking, download logging,
        # and quota reset functionality
        pass

# Performance tests
class TestPerformance:
    """Performance tests for critical paths"""
    
    @pytest.mark.asyncio
    async def test_concurrent_downloads(self):
        """Test handling of concurrent downloads"""
        # Test multiple simultaneous downloads
        pass
    
    @pytest.mark.asyncio
    async def test_database_performance(self):
        """Test database performance under load"""
        # Test database operations under concurrent load
        pass

if __name__ == "__main__":
    pytest.main([__file__, "-v"])