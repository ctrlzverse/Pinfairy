"""
Enhanced database service for Pinfairy Bot
Provides async database operations, connection pooling, and migration support
"""

import sqlite3
import aiosqlite
import asyncio
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Union
from contextlib import asynccontextmanager
from dataclasses import dataclass
from constants import DB_FILE, DB_SCHEMA_VERSION, DEFAULT_USER_SETTINGS, DEFAULT_DAILY_QUOTA
from exceptions import DatabaseException
from utils.logger import get_logger

logger = get_logger(__name__)

@dataclass
class QueryResult:
    """Structured query result with metadata"""
    data: Any
    execution_time: float
    rows_affected: int = 0

class ConnectionPool:
    """Optimized connection pool with health checks"""

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool = []
        self._lock = asyncio.Lock()
        self._created_connections = 0

    async def get_connection(self) -> aiosqlite.Connection:
        """Get connection from pool with health check"""
        async with self._lock:
            if self._pool:
                conn = self._pool.pop()
                # Health check
                try:
                    await conn.execute("SELECT 1")
                    return conn
                except Exception:
                    await conn.close()
                    # Fall through to create new connection

            # Create new connection
            if self._created_connections < self.pool_size * 2:  # Allow some overflow
                conn = await self._create_connection()
                self._created_connections += 1
                return conn
            else:
                # Wait for connection to be returned
                await asyncio.sleep(0.1)
                return await self.get_connection()

    async def return_connection(self, conn: aiosqlite.Connection):
        """Return connection to pool"""
        async with self._lock:
            if len(self._pool) < self.pool_size:
                self._pool.append(conn)
            else:
                await conn.close()
                self._created_connections -= 1

    async def _create_connection(self) -> aiosqlite.Connection:
        """Create optimized database connection"""
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row

        # Optimize SQLite settings
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute("PRAGMA journal_mode = WAL")
        await conn.execute("PRAGMA synchronous = NORMAL")
        await conn.execute("PRAGMA cache_size = 10000")
        await conn.execute("PRAGMA temp_store = MEMORY")
        await conn.execute("PRAGMA mmap_size = 268435456")  # 256MB
        await conn.execute("PRAGMA page_size = 4096")

        return conn

    async def close_all(self):
        """Close all connections in pool"""
        async with self._lock:
            for conn in self._pool:
                await conn.close()
            self._pool.clear()
            self._created_connections = 0

class DatabaseService:
    """Enhanced database service with async operations and optimized connection pooling"""

    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self._pool = ConnectionPool(db_path, pool_size=5)
        self._initialized = False
        self._cache = {}
        self._cache_ttl = {}
        self._query_stats = {
            'total_queries': 0,
            'total_time': 0.0,
            'slow_queries': 0
        }
    
    async def initialize(self):
        """Initialize database with schema and connection pool"""
        if self._initialized:
            return

        try:
            # Create database directory if it doesn't exist
            os.makedirs(os.path.dirname(self.db_path) if os.path.dirname(self.db_path) else '.', exist_ok=True)

            # Initialize schema
            await self._create_schema()

            # Run migrations
            await self._run_migrations()

            self._initialized = True
            logger.info("Database initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {str(e)}", exc_info=True)
            raise DatabaseException(f"Database initialization failed: {str(e)}")

    @asynccontextmanager
    async def get_connection(self):
        """Get connection from optimized pool"""
        conn = await self._pool.get_connection()
        try:
            yield conn
        finally:
            await self._pool.return_connection(conn)

    async def execute_query(self, query: str, params: tuple = None,
                           fetch_one: bool = False, fetch_all: bool = False) -> QueryResult:
        """Execute query with performance tracking and error handling"""
        start_time = time.time()

        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute(query, params or ())

                result = None
                rows_affected = cursor.rowcount

                if fetch_one:
                    result = await cursor.fetchone()
                elif fetch_all:
                    result = await cursor.fetchall()

                await conn.commit()

                execution_time = time.time() - start_time

                # Track query statistics
                self._query_stats['total_queries'] += 1
                self._query_stats['total_time'] += execution_time

                if execution_time > 1.0:  # Slow query threshold
                    self._query_stats['slow_queries'] += 1
                    logger.warning(f"Slow query detected: {execution_time:.2f}s - {query[:100]}...")

                return QueryResult(
                    data=result,
                    execution_time=execution_time,
                    rows_affected=rows_affected
                )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Query failed after {execution_time:.2f}s: {str(e)} - Query: {query[:100]}...")
            raise DatabaseException(f"Query execution failed: {str(e)}")

    def _get_cache_key(self, query: str, params: tuple = None) -> str:
        """Generate cache key for query"""
        return f"{hash(query)}_{hash(params) if params else 'none'}"

    async def execute_cached_query(self, query: str, params: tuple = None,
                                  cache_ttl: int = 300, fetch_one: bool = False,
                                  fetch_all: bool = False) -> QueryResult:
        """Execute query with caching support"""
        cache_key = self._get_cache_key(query, params)

        # Check cache
        if cache_key in self._cache:
            if time.time() < self._cache_ttl.get(cache_key, 0):
                logger.debug(f"Cache hit for query: {query[:50]}...")
                return self._cache[cache_key]
            else:
                # Cache expired
                del self._cache[cache_key]
                del self._cache_ttl[cache_key]

        # Execute query and cache result
        result = await self.execute_query(query, params, fetch_one, fetch_all)

        # Only cache SELECT queries
        if query.strip().upper().startswith('SELECT'):
            self._cache[cache_key] = result
            self._cache_ttl[cache_key] = time.time() + cache_ttl

        return result

    async def close(self):
        """Close all database connections"""
        await self._pool.close_all()
        self._initialized = False
        logger.info("Database connections closed")
    
    async def _create_schema(self):
        """Create database schema with indexes"""
        schema_sql = """
        -- Schema version table
        CREATE TABLE IF NOT EXISTS schema_version (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Download stats table
        CREATE TABLE IF NOT EXISTS download_stats (
            media_type TEXT PRIMARY KEY,
            count INTEGER NOT NULL DEFAULT 0,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Users table with enhanced fields
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            daily_quota INTEGER DEFAULT 100,
            downloads_today INTEGER DEFAULT 0,
            total_downloads INTEGER DEFAULT 0,
            quota_reset_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            settings TEXT DEFAULT '{"language": "id", "notifications": true, "download_quality": "high"}',
            is_banned BOOLEAN DEFAULT FALSE,
            ban_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Download history table with enhanced tracking
        CREATE TABLE IF NOT EXISTS download_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            url TEXT NOT NULL,
            file_size INTEGER,
            duration REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            error_code TEXT,
            ip_address TEXT,
            user_agent TEXT,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        
        -- Performance metrics table
        CREATE TABLE IF NOT EXISTS performance_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            cpu_usage REAL,
            memory_usage REAL,
            disk_usage REAL,
            response_time REAL,
            active_users INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            requests_per_minute INTEGER DEFAULT 0
        );
        
        -- Rate limiting table
        CREATE TABLE IF NOT EXISTS rate_limits (
            user_id INTEGER PRIMARY KEY,
            last_request TIMESTAMP,
            request_count INTEGER DEFAULT 0,
            window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        
        -- Cache table for frequently accessed data
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        -- Admin logs table
        CREATE TABLE IF NOT EXISTS admin_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            target_user_id INTEGER,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (admin_id) REFERENCES users(user_id),
            FOREIGN KEY (target_user_id) REFERENCES users(user_id)
        );
        
        -- Feedback table
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL, -- 'feedback' or 'feature_request'
            message TEXT NOT NULL,
            status TEXT DEFAULT 'pending', -- 'pending', 'reviewed', 'resolved'
            admin_response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        );
        """
        
        async with self.get_connection() as conn:
            await conn.executescript(schema_sql)
            await conn.commit()
        
        # Create indexes
        await self._create_indexes()
        
        # Insert initial data
        await self._insert_initial_data()
    
    async def _create_indexes(self):
        """Create database indexes for better performance"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
            "CREATE INDEX IF NOT EXISTS idx_users_last_active ON users(last_active)",
            "CREATE INDEX IF NOT EXISTS idx_download_history_user_id ON download_history(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_download_history_timestamp ON download_history(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_download_history_success ON download_history(success)",
            "CREATE INDEX IF NOT EXISTS idx_performance_metrics_timestamp ON performance_metrics(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_rate_limits_last_request ON rate_limits(last_request)",
            "CREATE INDEX IF NOT EXISTS idx_cache_expires_at ON cache(expires_at)",
            "CREATE INDEX IF NOT EXISTS idx_admin_logs_timestamp ON admin_logs(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status)",
            "CREATE INDEX IF NOT EXISTS idx_feedback_created_at ON feedback(created_at)"
        ]
        
        async with self.get_connection() as conn:
            for index_sql in indexes:
                await conn.execute(index_sql)
            await conn.commit()
    
    async def _insert_initial_data(self):
        """Insert initial data"""
        async with self.get_connection() as conn:
            # Insert download stats
            await conn.execute(
                "INSERT OR IGNORE INTO download_stats (media_type, count) VALUES (?, ?)",
                ('photo', 0)
            )
            await conn.execute(
                "INSERT OR IGNORE INTO download_stats (media_type, count) VALUES (?, ?)",
                ('video', 0)
            )
            await conn.execute(
                "INSERT OR IGNORE INTO download_stats (media_type, count) VALUES (?, ?)",
                ('board', 0)
            )
            await conn.commit()
    
    async def _run_migrations(self):
        """Run database migrations"""
        async with self.get_connection() as conn:
            # Check current schema version
            cursor = await conn.execute(
                "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
            )
            current_version = await cursor.fetchone()
            
            if not current_version:
                # First time setup
                await conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (DB_SCHEMA_VERSION,)
                )
                await conn.commit()
                logger.info(f"Database schema initialized with version {DB_SCHEMA_VERSION}")
    
    # User Management Methods
    async def create_user(self, user_id: int, username: str = None,
                         first_name: str = None, last_name: str = None) -> bool:
        """Create a new user with optimized query execution"""
        try:
            result = await self.execute_query("""
                INSERT OR IGNORE INTO users
                (user_id, username, first_name, last_name, settings)
                VALUES (?, ?, ?, ?, ?)
            """, (user_id, username, first_name, last_name, json.dumps(DEFAULT_USER_SETTINGS)))

            logger.debug(f"User {user_id} created/updated in {result.execution_time:.3f}s")
            return result.rows_affected > 0

        except Exception as e:
            logger.error(f"Failed to create user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to create user: {str(e)}")

    async def update_user_activity(self, user_id: int, username: str = None,
                                  first_name: str = None, last_name: str = None):
        """Update user's last active time and info with optimized query"""
        try:
            result = await self.execute_query("""
                INSERT INTO users (user_id, username, first_name, last_name, last_active)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    last_active = CURRENT_TIMESTAMP,
                    username = COALESCE(?, username),
                    first_name = COALESCE(?, first_name),
                    last_name = COALESCE(?, last_name),
                    updated_at = CURRENT_TIMESTAMP
            """, (user_id, username, first_name, last_name, username, first_name, last_name))

            logger.debug(f"User {user_id} activity updated in {result.execution_time:.3f}s")

        except Exception as e:
            logger.error(f"Failed to update user activity for {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to update user activity: {str(e)}")
    
    async def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get user profile and statistics with caching"""
        try:
            result = await self.execute_cached_query("""
                SELECT user_id, username, first_name, last_name, first_seen,
                       last_active, daily_quota, downloads_today, total_downloads,
                       quota_reset_at, settings, is_banned, ban_reason
                FROM users WHERE user_id = ?
            """, (user_id,), cache_ttl=300, fetch_one=True)

            if not result.data:
                return None

            row = result.data
            return {
                "user_id": row["user_id"],
                "username": row["username"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "first_seen": row["first_seen"],
                "last_active": row["last_active"],
                    "daily_quota": row["daily_quota"],
                    "downloads_today": row["downloads_today"],
                    "total_downloads": row["total_downloads"],
                    "quota_reset_at": row["quota_reset_at"],
                    "settings": json.loads(row["settings"]) if row["settings"] else DEFAULT_USER_SETTINGS,
                    "is_banned": bool(row["is_banned"]),
                    "ban_reason": row["ban_reason"]
                }
        except Exception as e:
            logger.error(f"Failed to get user profile for {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to get user profile: {str(e)}")
    
    async def update_user_settings(self, user_id: int, settings: Dict[str, Any]):
        """Update user settings"""
        try:
            # Get current settings
            current_profile = await self.get_user_profile(user_id)
            if not current_profile:
                await self.create_user(user_id)
                current_settings = DEFAULT_USER_SETTINGS.copy()
            else:
                current_settings = current_profile["settings"].copy()
            
            # Merge with new settings
            current_settings.update(settings)
            
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET settings = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (json.dumps(current_settings), user_id))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to update user settings for {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to update user settings: {str(e)}")
    
    # Download Management Methods
    async def log_download(self, user_id: int, media_type: str, url: str, 
                          success: bool, file_size: int = None, duration: float = None,
                          error_message: str = None, error_code: str = None):
        """Log download attempt"""
        try:
            async with self.get_connection() as conn:
                # Log download history
                await conn.execute("""
                    INSERT INTO download_history 
                    (user_id, media_type, url, file_size, duration, success, error_message, error_code)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, media_type, url, file_size, duration, success, error_message, error_code))
                
                if success:
                    # Update user stats
                    await conn.execute("""
                        UPDATE users SET 
                        downloads_today = downloads_today + 1,
                        total_downloads = total_downloads + 1,
                        updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (user_id,))
                    
                    # Update global stats
                    await conn.execute("""
                        UPDATE download_stats SET 
                        count = count + 1,
                        last_updated = CURRENT_TIMESTAMP
                        WHERE media_type = ?
                    """, (media_type,))
                
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to log download for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to log download: {str(e)}")
    
    async def get_download_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user's download history"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT media_type, url, file_size, duration, timestamp, 
                           success, error_message, error_code
                    FROM download_history
                    WHERE user_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (user_id, limit))
                rows = await cursor.fetchall()
                
                return [
                    {
                        "media_type": row["media_type"],
                        "url": row["url"],
                        "file_size": row["file_size"],
                        "duration": row["duration"],
                        "timestamp": row["timestamp"],
                        "success": bool(row["success"]),
                        "error_message": row["error_message"],
                        "error_code": row["error_code"]
                    }
                    for row in rows
                ]
        except Exception as e:
            logger.error(f"Failed to get download history for {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to get download history: {str(e)}")
    
    # Statistics Methods
    async def get_global_stats(self) -> Dict[str, int]:
        """Get global download statistics"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("SELECT media_type, count FROM download_stats")
                rows = await cursor.fetchall()
                return {row["media_type"]: row["count"] for row in rows}
        except Exception as e:
            logger.error(f"Failed to get global stats: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to get global stats: {str(e)}")
    
    async def get_leaderboard(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get top downloaders"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT username, total_downloads
                    FROM users
                    WHERE total_downloads > 0 AND is_banned = FALSE
                    ORDER BY total_downloads DESC
                    LIMIT ?
                """, (limit,))
                rows = await cursor.fetchall()
                return [(row["username"], row["total_downloads"]) for row in rows]
        except Exception as e:
            logger.error(f"Failed to get leaderboard: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to get leaderboard: {str(e)}")
    
    # Quota Management
    async def check_user_quota(self, user_id: int) -> Dict[str, Any]:
        """Check if user has remaining quota"""
        try:
            profile = await self.get_user_profile(user_id)
            if not profile:
                await self.create_user(user_id)
                return {"allowed": True, "remaining": DEFAULT_DAILY_QUOTA, "quota": DEFAULT_DAILY_QUOTA}
            
            # Check if quota needs reset
            quota_reset = datetime.fromisoformat(profile["quota_reset_at"])
            now = datetime.utcnow()
            
            if now.date() > quota_reset.date():
                # Reset daily quota
                async with self.get_connection() as conn:
                    await conn.execute("""
                        UPDATE users SET 
                        downloads_today = 0,
                        quota_reset_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                        WHERE user_id = ?
                    """, (user_id,))
                    await conn.commit()
                profile["downloads_today"] = 0
            
            remaining = profile["daily_quota"] - profile["downloads_today"]
            return {
                "allowed": remaining > 0 and not profile["is_banned"],
                "remaining": remaining,
                "quota": profile["daily_quota"],
                "is_banned": profile["is_banned"],
                "ban_reason": profile["ban_reason"]
            }
        except Exception as e:
            logger.error(f"Failed to check quota for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to check quota: {str(e)}")
    
    # Cache Methods
    async def set_cache(self, key: str, value: Any, ttl: int = 300):
        """Set cache value with TTL"""
        try:
            expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT OR REPLACE INTO cache (key, value, expires_at)
                    VALUES (?, ?, ?)
                """, (key, json.dumps(value), expires_at.isoformat()))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to set cache for key {key}: {str(e)}", exc_info=True)
    
    async def get_cache(self, key: str) -> Optional[Any]:
        """Get cache value if not expired"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT value FROM cache 
                    WHERE key = ? AND expires_at > CURRENT_TIMESTAMP
                """, (key,))
                row = await cursor.fetchone()
                
                if row:
                    return json.loads(row["value"])
                return None
        except Exception as e:
            logger.error(f"Failed to get cache for key {key}: {str(e)}", exc_info=True)
            return None
    
    async def clear_expired_cache(self):
        """Clear expired cache entries"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("DELETE FROM cache WHERE expires_at <= CURRENT_TIMESTAMP")
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to clear expired cache: {str(e)}", exc_info=True)
    
    # Performance Monitoring
    async def log_performance_metric(self, cpu_usage: float, memory_usage: float, 
                                   disk_usage: float, response_time: float = None,
                                   active_users: int = 0, error_count: int = 0,
                                   requests_per_minute: int = 0):
        """Log performance metrics"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    INSERT INTO performance_metrics 
                    (cpu_usage, memory_usage, disk_usage, response_time, 
                     active_users, error_count, requests_per_minute)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (cpu_usage, memory_usage, disk_usage, response_time, 
                      active_users, error_count, requests_per_minute))
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to log performance metrics: {str(e)}", exc_info=True)
    
    async def get_performance_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get performance statistics"""
        try:
            async with self.get_connection() as conn:
                cursor = await conn.execute("""
                    SELECT AVG(cpu_usage) as avg_cpu, AVG(memory_usage) as avg_memory,
                           AVG(disk_usage) as avg_disk, MAX(cpu_usage) as max_cpu,
                           MAX(memory_usage) as max_memory, MAX(disk_usage) as max_disk,
                           COUNT(*) as samples, AVG(response_time) as avg_response_time
                    FROM performance_metrics
                    WHERE timestamp > datetime('now', '-{} hours')
                """.format(hours))
                row = await cursor.fetchone()
                
                if not row or row["samples"] == 0:
                    return {"error": "No performance data available"}
                
                return {
                    "avg_cpu": round(row["avg_cpu"], 2) if row["avg_cpu"] else 0,
                    "avg_memory": round(row["avg_memory"], 2) if row["avg_memory"] else 0,
                    "avg_disk": round(row["avg_disk"], 2) if row["avg_disk"] else 0,
                    "max_cpu": round(row["max_cpu"], 2) if row["max_cpu"] else 0,
                    "max_memory": round(row["max_memory"], 2) if row["max_memory"] else 0,
                    "max_disk": round(row["max_disk"], 2) if row["max_disk"] else 0,
                    "avg_response_time": round(row["avg_response_time"], 3) if row["avg_response_time"] else 0,
                    "samples": row["samples"]
                }
        except Exception as e:
            logger.error(f"Failed to get performance stats: {str(e)}", exc_info=True)
            return {"error": f"Failed to get performance stats: {str(e)}"}
    
    # Admin Methods
    async def ban_user(self, admin_id: int, user_id: int, reason: str):
        """Ban a user"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_banned = TRUE, ban_reason = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (reason, user_id))
                
                await conn.execute("""
                    INSERT INTO admin_logs (admin_id, action, target_user_id, details)
                    VALUES (?, 'ban_user', ?, ?)
                """, (admin_id, user_id, reason))
                
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to ban user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to ban user: {str(e)}")
    
    async def unban_user(self, admin_id: int, user_id: int):
        """Unban a user"""
        try:
            async with self.get_connection() as conn:
                await conn.execute("""
                    UPDATE users SET is_banned = FALSE, ban_reason = NULL, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                """, (user_id,))
                
                await conn.execute("""
                    INSERT INTO admin_logs (admin_id, action, target_user_id)
                    VALUES (?, 'unban_user', ?)
                """, (admin_id, user_id))
                
                await conn.commit()
        except Exception as e:
            logger.error(f"Failed to unban user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to unban user: {str(e)}")
    
    # Cleanup Methods
    async def cleanup_old_data(self, days: int = 30):
        """Clean up old data"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            async with self.get_connection() as conn:
                # Clean old download history
                await conn.execute("""
                    DELETE FROM download_history 
                    WHERE timestamp < ? AND success = FALSE
                """, (cutoff_date.isoformat(),))
                
                # Clean old performance metrics
                await conn.execute("""
                    DELETE FROM performance_metrics 
                    WHERE timestamp < ?
                """, (cutoff_date.isoformat(),))
                
                # Clean expired cache
                await conn.execute("DELETE FROM cache WHERE expires_at <= CURRENT_TIMESTAMP")
                
                await conn.commit()
                logger.info(f"Cleaned up data older than {days} days")
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {str(e)}", exc_info=True)
    
    async def close(self):
        """Close all connections"""
        async with self._lock:
            for conn in self._connection_pool:
                await conn.close()
            self._connection_pool.clear()
        logger.info("Database connections closed")

# Global database instance
db_service = DatabaseService()

# Convenience functions for backward compatibility
async def init_db():
    """Initialize database"""
    await db_service.initialize()

async def get_user_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user profile"""
    return await db_service.get_user_profile(user_id)

async def update_user_activity(user_id: int, username: str = None):
    """Update user activity"""
    await db_service.update_user_activity(user_id, username)

async def log_download(user_id: int, media_type: str, url: str, success: bool, **kwargs):
    """Log download"""
    await db_service.log_download(user_id, media_type, url, success, **kwargs)