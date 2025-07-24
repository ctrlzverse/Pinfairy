"""
Comprehensive handler tests for Pinfairy Bot
Tests command handlers, error handling, validation, and performance
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from handlers.commands import (
    handle_start, handle_pinterest_photo, handle_pinterest_video,
    handler_wrapper, handler_stats, error_handler
)
from exceptions import (
    RateLimitException, QuotaExceededException, 
    ValidationException, ErrorContext
)


class MockEvent:
    """Mock Telegram event for testing"""
    
    def __init__(self, sender_id=12345, username="test_user", 
                 first_name="Test", text="", pattern_match=None):
        self.sender_id = sender_id
        self.sender = MagicMock()
        self.sender.username = username
        self.sender.first_name = first_name
        self.text = text
        self.pattern_match = pattern_match
        self.reply_calls = []
        self.edit_calls = []
    
    async def reply(self, message, **kwargs):
        """Mock reply method"""
        self.reply_calls.append((message, kwargs))
        return MagicMock()
    
    async def edit(self, message, **kwargs):
        """Mock edit method"""
        self.edit_calls.append((message, kwargs))
        return MagicMock()


class TestHandlerWrapper:
    """Test handler wrapper decorator functionality"""
    
    @pytest.fixture
    def mock_event(self):
        """Create mock event for testing"""
        return MockEvent()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.update_user_activity')
    @patch('handlers.commands.check_rate_limit')
    @patch('handlers.commands.check_user_quota')
    async def test_successful_handler_execution(self, mock_quota, mock_rate, 
                                               mock_activity, mock_event):
        """Test successful handler execution with all checks passing"""
        # Mock successful checks
        mock_rate.return_value = {'allowed': True}
        mock_quota.return_value = {'allowed': True}
        mock_activity.return_value = None
        
        # Create test handler
        @handler_wrapper("test_handler", require_url=False, check_quota=True)
        async def test_handler(event):
            return "success"
        
        result = await test_handler(mock_event)
        assert result == "success"
        
        # Verify checks were called
        mock_activity.assert_called_once()
        mock_rate.assert_called_once()
        mock_quota.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.update_user_activity')
    @patch('handlers.commands.check_rate_limit')
    async def test_rate_limit_handling(self, mock_rate, mock_activity, mock_event):
        """Test rate limit exception handling"""
        # Mock rate limit exceeded
        mock_rate.return_value = {'allowed': False, 'retry_after': 30}
        mock_activity.return_value = None
        
        @handler_wrapper("test_handler", require_url=False, check_quota=False)
        async def test_handler(event):
            return "success"
        
        await test_handler(mock_event)
        
        # Should have sent error message
        assert len(mock_event.reply_calls) > 0
        error_message = mock_event.reply_calls[0][0]
        assert "30 detik" in error_message or "tunggu" in error_message.lower()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.update_user_activity')
    @patch('handlers.commands.check_rate_limit')
    @patch('handlers.commands.check_user_quota')
    async def test_quota_exceeded_handling(self, mock_quota, mock_rate, 
                                          mock_activity, mock_event):
        """Test quota exceeded exception handling"""
        # Mock quota exceeded
        mock_rate.return_value = {'allowed': True}
        mock_quota.return_value = {'allowed': False, 'remaining': 0}
        mock_activity.return_value = None
        
        @handler_wrapper("test_handler", require_url=False, check_quota=True)
        async def test_handler(event):
            return "success"
        
        await test_handler(mock_event)
        
        # Should have sent error message
        assert len(mock_event.reply_calls) > 0
        error_message = mock_event.reply_calls[0][0]
        assert "quota" in error_message.lower()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.update_user_activity')
    @patch('handlers.commands.check_rate_limit')
    @patch('handlers.commands.validate_url')
    async def test_url_validation(self, mock_validate, mock_rate, 
                                 mock_activity, mock_event):
        """Test URL validation in handler wrapper"""
        # Setup mocks
        mock_rate.return_value = {'allowed': True}
        mock_activity.return_value = None
        mock_validate.return_value = {'is_valid': True}
        
        # Create event with URL
        pattern_match = MagicMock()
        pattern_match.group.return_value = "https://pinterest.com/pin/123456789"
        mock_event.pattern_match = pattern_match
        
        @handler_wrapper("test_handler", require_url=True, check_quota=False)
        async def test_handler(event):
            return "success"
        
        result = await test_handler(mock_event)
        assert result == "success"
        
        # Verify URL validation was called
        mock_validate.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.update_user_activity')
    async def test_missing_url_handling(self, mock_activity, mock_event):
        """Test handling of missing URL when required"""
        mock_activity.return_value = None
        
        # Create event without URL
        pattern_match = MagicMock()
        pattern_match.group.return_value = None
        mock_event.pattern_match = pattern_match
        
        @handler_wrapper("test_handler", require_url=True, check_quota=False)
        async def test_handler(event):
            return "success"
        
        await test_handler(mock_event)
        
        # Should have sent error message
        assert len(mock_event.reply_calls) > 0
        error_message = mock_event.reply_calls[0][0]
        assert "tidak valid" in error_message.lower()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.update_user_activity')
    async def test_handler_exception_handling(self, mock_activity, mock_event):
        """Test general exception handling in wrapper"""
        mock_activity.return_value = None
        
        @handler_wrapper("test_handler", require_url=False, check_quota=False)
        async def test_handler(event):
            raise ValueError("Test error")
        
        await test_handler(mock_event)
        
        # Should have sent error message
        assert len(mock_event.reply_calls) > 0
        error_message = mock_event.reply_calls[0][0]
        assert "❌" in error_message
    
    @pytest.mark.asyncio
    @patch('handlers.commands.update_user_activity')
    async def test_performance_tracking(self, mock_activity, mock_event):
        """Test performance tracking in handler wrapper"""
        mock_activity.return_value = None
        
        initial_calls = handler_stats['total_calls']
        initial_time = handler_stats['total_time']
        
        @handler_wrapper("test_handler", require_url=False, check_quota=False)
        async def test_handler(event):
            await asyncio.sleep(0.01)  # Small delay
            return "success"
        
        await test_handler(mock_event)
        
        # Performance stats should be updated
        assert handler_stats['total_calls'] > initial_calls
        assert handler_stats['total_time'] > initial_time
        assert 'test_handler' in handler_stats['handler_times']


class TestSpecificHandlers:
    """Test specific command handlers"""
    
    @pytest.fixture
    def mock_event(self):
        """Create mock event for testing"""
        return MockEvent()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.process_start_command')
    async def test_handle_start(self, mock_process, mock_event):
        """Test start command handler"""
        mock_process.return_value = None
        
        # This will be wrapped by the decorator, so we need to mock the dependencies
        with patch('handlers.commands.update_user_activity'):
            await handle_start(mock_event)
        
        mock_process.assert_called_once_with(mock_event)
    
    @pytest.mark.asyncio
    @patch('handlers.commands.process_pinterest_photo')
    @patch('handlers.commands.log_download')
    async def test_handle_pinterest_photo(self, mock_log, mock_process, mock_event):
        """Test Pinterest photo handler"""
        # Setup URL pattern match
        pattern_match = MagicMock()
        pattern_match.group.return_value = "https://pinterest.com/pin/123456789"
        mock_event.pattern_match = pattern_match
        
        mock_process.return_value = None
        mock_log.return_value = None
        
        # Mock all the wrapper dependencies
        with patch('handlers.commands.update_user_activity'), \
             patch('handlers.commands.check_rate_limit', return_value={'allowed': True}), \
             patch('handlers.commands.check_user_quota', return_value={'allowed': True}), \
             patch('handlers.commands.validate_url', return_value={'is_valid': True}):
            
            await handle_pinterest_photo(mock_event)
        
        mock_process.assert_called_once()
        mock_log.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('handlers.commands.process_pinterest_video')
    @patch('handlers.commands.log_download')
    async def test_handle_pinterest_video(self, mock_log, mock_process, mock_event):
        """Test Pinterest video handler"""
        # Setup URL pattern match
        pattern_match = MagicMock()
        pattern_match.group.return_value = "https://pinterest.com/pin/123456789"
        mock_event.pattern_match = pattern_match
        
        mock_process.return_value = None
        mock_log.return_value = None
        
        # Mock all the wrapper dependencies
        with patch('handlers.commands.update_user_activity'), \
             patch('handlers.commands.check_rate_limit', return_value={'allowed': True}), \
             patch('handlers.commands.check_user_quota', return_value={'allowed': True}), \
             patch('handlers.commands.validate_url', return_value={'is_valid': True}):
            
            await handle_pinterest_video(mock_event)
        
        mock_process.assert_called_once()
        mock_log.assert_called_once()


class TestErrorHandling:
    """Test error handling functionality"""
    
    def test_error_context_creation(self):
        """Test error context creation"""
        context = ErrorContext(
            user_id=12345,
            username="test_user",
            command="test_command",
            url="https://pinterest.com/test"
        )
        
        assert context.user_id == 12345
        assert context.username == "test_user"
        assert context.command == "test_command"
        assert context.url == "https://pinterest.com/test"
        assert context.timestamp is not None
    
    def test_error_handler_stats(self):
        """Test error handler statistics"""
        initial_stats = error_handler.get_error_stats()
        
        # Simulate handling an error
        test_exception = ValueError("Test error")
        error_handler.handle_exception(test_exception)
        
        updated_stats = error_handler.get_error_stats()
        
        # Stats should be updated
        assert updated_stats['total_errors'] > initial_stats['total_errors']
        assert 'ValueError' in updated_stats['error_types']


class TestPerformanceMonitoring:
    """Test performance monitoring in handlers"""
    
    @pytest.mark.asyncio
    async def test_handler_performance_tracking(self):
        """Test that handler performance is tracked"""
        initial_stats = handler_stats.copy()
        
        # Create a test handler that takes some time
        @handler_wrapper("perf_test", require_url=False, check_quota=False)
        async def slow_handler(event):
            await asyncio.sleep(0.01)
            return "done"
        
        mock_event = MockEvent()
        
        with patch('handlers.commands.update_user_activity'):
            await slow_handler(mock_event)
        
        # Performance should be tracked
        assert handler_stats['total_calls'] > initial_stats['total_calls']
        assert handler_stats['total_time'] > initial_stats['total_time']
        assert 'perf_test' in handler_stats['handler_times']
    
    @pytest.mark.asyncio
    async def test_concurrent_handler_execution(self):
        """Test concurrent handler execution performance"""
        @handler_wrapper("concurrent_test", require_url=False, check_quota=False)
        async def concurrent_handler(event):
            await asyncio.sleep(0.01)
            return f"done_{event.sender_id}"
        
        # Create multiple mock events
        events = [MockEvent(sender_id=i) for i in range(10)]
        
        with patch('handlers.commands.update_user_activity'):
            # Execute handlers concurrently
            tasks = [concurrent_handler(event) for event in events]
            results = await asyncio.gather(*tasks)
        
        # All should complete successfully
        assert len(results) == 10
        for i, result in enumerate(results):
            assert result == f"done_{i}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
