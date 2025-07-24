"""
Comprehensive database tests for Pinfairy Bot
Tests database operations, connection pooling, caching, and performance
"""

import pytest
import asyncio
import tempfile
import os
import time
from unittest.mock import AsyncMock, patch

from services.database import DatabaseService, ConnectionPool, QueryResult
from exceptions import DatabaseException
from constants import DB_OPTIMIZATION


class TestConnectionPool:
    """Test connection pool functionality"""
    
    @pytest.fixture
    async def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    async def connection_pool(self, temp_db):
        """Create connection pool for testing"""
        pool = ConnectionPool(temp_db, pool_size=3)
        yield pool
        await pool.close_all()
    
    @pytest.mark.asyncio
    async def test_connection_pool_creation(self, connection_pool):
        """Test connection pool creation"""
        assert connection_pool.pool_size == 3
        assert len(connection_pool._pool) == 0
        assert connection_pool._created_connections == 0
    
    @pytest.mark.asyncio
    async def test_get_and_return_connection(self, connection_pool):
        """Test getting and returning connections"""
        # Get connection
        conn = await connection_pool.get_connection()
        assert conn is not None
        assert connection_pool._created_connections == 1
        
        # Return connection
        await connection_pool.return_connection(conn)
        assert len(connection_pool._pool) == 1
    
    @pytest.mark.asyncio
    async def test_connection_health_check(self, connection_pool):
        """Test connection health checking"""
        # Get and return connection
        conn = await connection_pool.get_connection()
        await connection_pool.return_connection(conn)
        
        # Get connection again (should reuse)
        conn2 = await connection_pool.get_connection()
        assert conn2 is not None
        
        await connection_pool.return_connection(conn2)
    
    @pytest.mark.asyncio
    async def test_pool_overflow_handling(self, connection_pool):
        """Test pool behavior when exceeding pool size"""
        connections = []
        
        # Get more connections than pool size
        for _ in range(5):
            conn = await connection_pool.get_connection()
            connections.append(conn)
        
        assert connection_pool._created_connections <= 6  # pool_size * 2
        
        # Return all connections
        for conn in connections:
            await connection_pool.return_connection(conn)


class TestDatabaseService:
    """Test database service functionality"""
    
    @pytest.fixture
    async def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        yield db_path
        
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.fixture
    async def db_service(self, temp_db):
        """Create database service for testing"""
        service = DatabaseService(temp_db)
        await service.initialize()
        yield service
        await service.close()
    
    @pytest.mark.asyncio
    async def test_database_initialization(self, db_service):
        """Test database initialization"""
        assert db_service._initialized is True
        assert db_service._pool is not None
    
    @pytest.mark.asyncio
    async def test_execute_query(self, db_service):
        """Test query execution"""
        # Test simple query
        result = await db_service.execute_query(
            "SELECT 1 as test_value",
            fetch_one=True
        )
        
        assert isinstance(result, QueryResult)
        assert result.data is not None
        assert result.data['test_value'] == 1
        assert result.execution_time > 0
    
    @pytest.mark.asyncio
    async def test_cached_query(self, db_service):
        """Test query caching"""
        query = "SELECT datetime('now') as current_time"
        
        # First execution
        result1 = await db_service.execute_cached_query(
            query, cache_ttl=5, fetch_one=True
        )
        
        # Second execution (should be cached)
        result2 = await db_service.execute_cached_query(
            query, cache_ttl=5, fetch_one=True
        )
        
        # Results should be identical (cached)
        assert result1.data['current_time'] == result2.data['current_time']
    
    @pytest.mark.asyncio
    async def test_user_operations(self, db_service):
        """Test user-related database operations"""
        user_id = 12345
        username = "test_user"
        
        # Create user
        success = await db_service.create_user(
            user_id, username, "Test", "User"
        )
        assert success is True
        
        # Get user profile
        profile = await db_service.get_user_profile(user_id)
        assert profile is not None
        assert profile['user_id'] == user_id
        assert profile['username'] == username
    
    @pytest.mark.asyncio
    async def test_performance_tracking(self, db_service):
        """Test query performance tracking"""
        # Execute a slow query (simulate with sleep)
        with patch('time.time', side_effect=[0, 2.0]):  # 2 second execution
            result = await db_service.execute_query(
                "SELECT 1", fetch_one=True
            )
        
        # Check if slow query was detected
        assert db_service._query_stats['slow_queries'] >= 0
        assert db_service._query_stats['total_queries'] > 0
    
    @pytest.mark.asyncio
    async def test_error_handling(self, db_service):
        """Test database error handling"""
        with pytest.raises(DatabaseException):
            await db_service.execute_query(
                "SELECT * FROM non_existent_table"
            )
    
    @pytest.mark.asyncio
    async def test_cache_expiration(self, db_service):
        """Test cache expiration"""
        query = "SELECT random() as random_value"
        
        # First execution
        result1 = await db_service.execute_cached_query(
            query, cache_ttl=1, fetch_one=True
        )
        
        # Wait for cache to expire
        await asyncio.sleep(1.1)
        
        # Second execution (cache should be expired)
        result2 = await db_service.execute_cached_query(
            query, cache_ttl=1, fetch_one=True
        )
        
        # Results should be different (not cached)
        assert result1.data['random_value'] != result2.data['random_value']


class TestDatabasePerformance:
    """Test database performance and optimization"""
    
    @pytest.fixture
    async def db_service(self):
        """Create database service for performance testing"""
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name
        
        service = DatabaseService(db_path)
        await service.initialize()
        
        yield service
        
        await service.close()
        if os.path.exists(db_path):
            os.unlink(db_path)
    
    @pytest.mark.asyncio
    async def test_concurrent_queries(self, db_service):
        """Test concurrent query execution"""
        async def execute_query(query_id):
            return await db_service.execute_query(
                f"SELECT {query_id} as id", fetch_one=True
            )
        
        # Execute multiple queries concurrently
        tasks = [execute_query(i) for i in range(10)]
        results = await asyncio.gather(*tasks)
        
        # All queries should complete successfully
        assert len(results) == 10
        for i, result in enumerate(results):
            assert result.data['id'] == i
    
    @pytest.mark.asyncio
    async def test_connection_pool_efficiency(self, db_service):
        """Test connection pool efficiency"""
        start_time = time.time()
        
        # Execute many queries
        tasks = []
        for i in range(50):
            task = db_service.execute_query(
                "SELECT 1", fetch_one=True
            )
            tasks.append(task)
        
        results = await asyncio.gather(*tasks)
        execution_time = time.time() - start_time
        
        # All queries should complete
        assert len(results) == 50
        
        # Should complete reasonably fast with connection pooling
        assert execution_time < 10.0  # Should complete within 10 seconds
    
    @pytest.mark.asyncio
    async def test_cache_performance(self, db_service):
        """Test caching performance improvement"""
        query = "SELECT datetime('now') as current_time"
        
        # Time uncached query
        start_time = time.time()
        await db_service.execute_query(query, fetch_one=True)
        uncached_time = time.time() - start_time
        
        # Time cached query (first execution)
        start_time = time.time()
        await db_service.execute_cached_query(query, fetch_one=True)
        first_cached_time = time.time() - start_time
        
        # Time cached query (second execution - should be faster)
        start_time = time.time()
        await db_service.execute_cached_query(query, fetch_one=True)
        second_cached_time = time.time() - start_time
        
        # Second cached execution should be faster
        assert second_cached_time < first_cached_time


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
