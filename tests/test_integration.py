"""
Integration tests for Pinfairy Bot
Tests end-to-end functionality and component integration
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import AsyncMock, MagicMock, patch

from bot import PinfairyBot
from services.database import DatabaseService
from services.pinterest import PinterestService
from handlers.commands import handle_start, handle_pinterest_photo
from exceptions import ErrorHandler, ErrorContext


@pytest.mark.integration
class TestBotIntegration:
    """Test bot integration and lifecycle"""
    
    @pytest.fixture
    async def temp_db_path(self):
        """Create temporary database path"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    @patch('bot.TelegramClient')
    @patch('bot.init_db')
    async def test_bot_initialization(self, mock_init_db, mock_client_class, temp_db_path):
        """Test complete bot initialization"""
        # Mock Telegram client
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.is_connected = MagicMock(return_value=True)
        mock_client_class.return_value = mock_client
        
        # Mock database initialization
        mock_init_db.return_value = None
        
        # Create bot instance
        bot = PinfairyBot()
        
        # Mock environment variables
        with patch.dict(os.environ, {
            'API_ID': '12345',
            'API_HASH': 'test_hash',
            'BOT_TOKEN': 'test_token'
        }):
            await bot.initialize()
        
        # Verify initialization
        assert bot.client is not None
        assert bot.config is not None
        assert bot._running is False
        mock_client.start.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('bot.TelegramClient')
    async def test_bot_shutdown(self, mock_client_class):
        """Test bot graceful shutdown"""
        # Mock Telegram client
        mock_client = AsyncMock()
        mock_client.is_connected = MagicMock(return_value=True)
        mock_client.disconnect = AsyncMock()
        mock_client_class.return_value = mock_client
        
        bot = PinfairyBot()
        bot.client = mock_client
        bot._running = True
        
        # Test shutdown
        await bot.shutdown()
        
        assert bot._running is False
        mock_client.disconnect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_monitoring(self):
        """Test bot health monitoring functionality"""
        bot = PinfairyBot()
        bot._running = True
        bot._performance_metrics['start_time'] = asyncio.get_event_loop().time()
        
        # Mock client
        mock_client = AsyncMock()
        mock_client.is_connected = MagicMock(return_value=True)
        bot.client = mock_client
        
        # Start health monitoring (should not raise exceptions)
        bot._start_health_monitoring()
        
        # Wait a bit for health check to run
        await asyncio.sleep(0.1)
        
        # Stop monitoring
        bot._running = False
        
        # Cleanup background tasks
        for task in bot._background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.mark.integration
class TestServiceIntegration:
    """Test service integration"""
    
    @pytest.fixture
    async def database_service(self):
        """Create database service for integration testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        service = DatabaseService(db_path)
        await service.initialize()
        
        yield service
        
        await service.close()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    async def pinterest_service(self):
        """Create Pinterest service for integration testing"""
        service = PinterestService()
        await service.initialize()
        
        yield service
        
        await service.close()
    
    @pytest.mark.asyncio
    async def test_database_pinterest_integration(self, database_service, pinterest_service):
        """Test database and Pinterest service integration"""
        user_id = 12345
        username = "test_user"
        url = "https://pinterest.com/pin/123456789"
        
        # Create user in database
        success = await database_service.create_user(user_id, username, "Test", "User")
        assert success is True
        
        # Get user profile
        profile = await database_service.get_user_profile(user_id)
        assert profile is not None
        assert profile['user_id'] == user_id
        
        # Test caching integration
        cache_key = f"pinterest_data_{url}"
        test_data = {"title": "Test Pin", "url": url}
        
        await pinterest_service._set_cached_data(cache_key, test_data)
        cached_data = await pinterest_service._get_cached_data(cache_key)
        
        assert cached_data == test_data
    
    @pytest.mark.asyncio
    async def test_error_handling_integration(self, database_service):
        """Test error handling across services"""
        error_handler = ErrorHandler()
        
        # Test database error handling
        try:
            await database_service.execute_query("INVALID SQL QUERY")
        except Exception as e:
            user_message = error_handler.handle_exception(
                e, 
                ErrorContext(user_id=12345, command="test")
            )
            assert "❌" in user_message
            assert isinstance(user_message, str)
        
        # Check error statistics
        stats = error_handler.get_error_stats()
        assert stats['total_errors'] > 0


@pytest.mark.integration
class TestHandlerIntegration:
    """Test handler integration with services"""
    
    @pytest.fixture
    def mock_event(self):
        """Create comprehensive mock event"""
        event = MagicMock()
        event.sender_id = 12345
        event.sender.username = "test_user"
        event.sender.first_name = "Test"
        event.sender.last_name = "User"
        event.text = "/start"
        event.reply = AsyncMock()
        event.edit = AsyncMock()
        
        # Mock pattern match for URL commands
        pattern_match = MagicMock()
        pattern_match.group.return_value = "https://pinterest.com/pin/123456789"
        event.pattern_match = pattern_match
        
        return event
    
    @pytest.mark.asyncio
    @patch('handlers.commands.process_start_command')
    @patch('handlers.commands.update_user_activity')
    async def test_start_handler_integration(self, mock_activity, mock_process, mock_event):
        """Test start handler integration"""
        mock_process.return_value = None
        mock_activity.return_value = None
        
        await handle_start(mock_event)
        
        # Verify handler was called
        mock_process.assert_called_once_with(mock_event)
        mock_activity.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.process_pinterest_photo')
    @patch('handlers.commands.log_download')
    @patch('handlers.commands.update_user_activity')
    @patch('handlers.commands.check_rate_limit')
    @patch('handlers.commands.check_user_quota')
    @patch('handlers.commands.validate_url')
    async def test_pinterest_photo_handler_integration(self, mock_validate, mock_quota, 
                                                      mock_rate, mock_activity, mock_log, 
                                                      mock_process, mock_event):
        """Test Pinterest photo handler integration"""
        # Setup mocks
        mock_validate.return_value = {'is_valid': True}
        mock_rate.return_value = {'allowed': True}
        mock_quota.return_value = {'allowed': True}
        mock_activity.return_value = None
        mock_process.return_value = None
        mock_log.return_value = None
        
        await handle_pinterest_photo(mock_event)
        
        # Verify all components were called
        mock_validate.assert_called_once()
        mock_rate.assert_called_once()
        mock_quota.assert_called_once()
        mock_activity.assert_called_once()
        mock_process.assert_called_once()
        mock_log.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.update_user_activity')
    @patch('handlers.commands.check_rate_limit')
    @patch('handlers.commands.check_user_quota')
    async def test_handler_error_propagation(self, mock_quota, mock_rate, 
                                           mock_activity, mock_event):
        """Test error propagation through handler stack"""
        # Setup mocks
        mock_activity.return_value = None
        mock_rate.return_value = {'allowed': True}
        mock_quota.return_value = {'allowed': False, 'remaining': 0}
        
        await handle_pinterest_photo(mock_event)
        
        # Should have sent error message due to quota exceeded
        assert len(mock_event.reply.call_args_list) > 0
        error_message = mock_event.reply.call_args_list[0][0][0]
        assert "quota" in error_message.lower()


@pytest.mark.integration
class TestPerformanceIntegration:
    """Test performance across integrated components"""
    
    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self):
        """Test concurrent database operations performance"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        try:
            service = DatabaseService(db_path)
            await service.initialize()
            
            # Create multiple concurrent operations
            async def create_user_task(user_id):
                return await service.create_user(
                    user_id, f"user_{user_id}", "Test", "User"
                )
            
            # Execute concurrent operations
            tasks = [create_user_task(i) for i in range(20)]
            results = await asyncio.gather(*tasks)
            
            # All operations should succeed
            assert all(results)
            
            # Verify users were created
            for i in range(20):
                profile = await service.get_user_profile(i)
                assert profile is not None
                assert profile['user_id'] == i
            
            await service.close()
            
        finally:
            if os.path.exists(db_path):
                os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_handler_performance_under_load(self):
        """Test handler performance under load"""
        from handlers.commands import handler_stats
        
        initial_stats = handler_stats.copy()
        
        # Create multiple mock events
        events = []
        for i in range(10):
            event = MagicMock()
            event.sender_id = i
            event.sender.username = f"user_{i}"
            event.sender.first_name = "Test"
            event.reply = AsyncMock()
            events.append(event)
        
        # Execute handlers concurrently
        with patch('handlers.commands.process_start_command'), \
             patch('handlers.commands.update_user_activity'):
            
            tasks = [handle_start(event) for event in events]
            await asyncio.gather(*tasks)
        
        # Performance should be tracked
        assert handler_stats['total_calls'] > initial_stats['total_calls']
        assert handler_stats['total_time'] > initial_stats['total_time']


@pytest.mark.integration
class TestEndToEndScenarios:
    """Test complete end-to-end scenarios"""
    
    @pytest.mark.asyncio
    @patch('bot.TelegramClient')
    @patch('bot.init_db')
    async def test_complete_bot_lifecycle(self, mock_init_db, mock_client_class):
        """Test complete bot lifecycle from start to shutdown"""
        # Mock dependencies
        mock_client = AsyncMock()
        mock_client.start = AsyncMock()
        mock_client.is_connected = MagicMock(return_value=True)
        mock_client.disconnect = AsyncMock()
        mock_client.add_event_handler = MagicMock()
        mock_client_class.return_value = mock_client
        mock_init_db.return_value = None
        
        # Create and initialize bot
        bot = PinfairyBot()
        
        with patch.dict(os.environ, {
            'API_ID': '12345',
            'API_HASH': 'test_hash',
            'BOT_TOKEN': 'test_token'
        }):
            await bot.initialize()
        
        # Verify initialization
        assert bot.client is not None
        assert bot.config is not None
        
        # Test shutdown
        await bot.shutdown()
        
        # Verify cleanup
        assert bot._running is False
        mock_client.disconnect.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
