"""
Monitoring and performance service for Pinfairy Bot
Provides system monitoring, health checks, and performance metrics
"""

import asyncio
import psutil
import time
import platform
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass

from constants import PERFORMANCE_LOG_INTERVAL
from exceptions import DatabaseException
from utils.logger import get_logger
from services.database import db_service

logger = get_logger(__name__)

@dataclass
class SystemMetrics:
    """System metrics data class"""
    timestamp: datetime
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    network_io: Dict[str, int]
    process_count: int
    uptime: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "cpu_usage": self.cpu_usage,
            "memory_usage": self.memory_usage,
            "disk_usage": self.disk_usage,
            "network_io": self.network_io,
            "process_count": self.process_count,
            "uptime": self.uptime
        }

@dataclass
class ApplicationMetrics:
    """Application-specific metrics"""
    active_users: int
    requests_per_minute: int
    error_count: int
    cache_hit_rate: float
    database_connections: int
    response_times: List[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "active_users": self.active_users,
            "requests_per_minute": self.requests_per_minute,
            "error_count": self.error_count,
            "cache_hit_rate": self.cache_hit_rate,
            "database_connections": self.database_connections,
            "avg_response_time": sum(self.response_times) / len(self.response_times) if self.response_times else 0,
            "response_times": self.response_times
        }

class SystemMonitor:
    """Monitors system resources and performance"""
    
    def __init__(self):
        self.start_time = datetime.utcnow()
        self._last_network_io = None
        self._monitoring = False
        self._monitor_task = None
    
    def get_system_metrics(self) -> SystemMetrics:
        """Get current system metrics"""
        try:
            # CPU usage
            cpu_usage = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            memory_usage = memory.percent
            
            # Disk usage
            disk = psutil.disk_usage('/')
            disk_usage = disk.percent
            
            # Network I/O
            network_io = psutil.net_io_counters()
            network_data = {
                "bytes_sent": network_io.bytes_sent,
                "bytes_recv": network_io.bytes_recv,
                "packets_sent": network_io.packets_sent,
                "packets_recv": network_io.packets_recv
            }
            
            # Process count
            process_count = len(psutil.pids())
            
            # Uptime
            uptime = (datetime.utcnow() - self.start_time).total_seconds()
            
            return SystemMetrics(
                timestamp=datetime.utcnow(),
                cpu_usage=cpu_usage,
                memory_usage=memory_usage,
                disk_usage=disk_usage,
                network_io=network_data,
                process_count=process_count,
                uptime=uptime
            )
            
        except Exception as e:
            logger.error(f"Failed to get system metrics: {str(e)}", exc_info=True)
            raise
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get static system information"""
        try:
            return {
                "platform": platform.platform(),
                "python_version": platform.python_version(),
                "cpu_count": psutil.cpu_count(),
                "total_memory": psutil.virtual_memory().total,
                "total_disk": psutil.disk_usage('/').total,
                "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                "hostname": platform.node()
            }
        except Exception as e:
            logger.error(f"Failed to get system info: {str(e)}")
            return {"error": str(e)}
    
    async def start_monitoring(self):
        """Start continuous monitoring"""
        if self._monitoring:
            return
        
        self._monitoring = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())
        logger.info("System monitoring started")
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        self._monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
        logger.info("System monitoring stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._monitoring:
            try:
                metrics = self.get_system_metrics()
                
                # Log to database
                await db_service.log_performance_metric(
                    cpu_usage=metrics.cpu_usage,
                    memory_usage=metrics.memory_usage,
                    disk_usage=metrics.disk_usage
                )
                
                # Log performance metrics
                logger.log_performance(
                    operation="system_monitoring",
                    duration=0,
                    cpu_usage=metrics.cpu_usage,
                    memory_usage=metrics.memory_usage,
                    disk_usage=metrics.disk_usage
                )
                
                await asyncio.sleep(PERFORMANCE_LOG_INTERVAL)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Wait before retrying

class ApplicationMonitor:
    """Monitors application-specific metrics"""
    
    def __init__(self):
        self.request_times = []
        self.error_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.active_users = set()
        self._reset_time = datetime.utcnow()
    
    def record_request(self, user_id: int, duration: float, success: bool = True):
        """Record a request"""
        self.request_times.append(duration)
        self.active_users.add(user_id)
        
        if not success:
            self.error_count += 1
        
        # Keep only last 1000 request times
        if len(self.request_times) > 1000:
            self.request_times = self.request_times[-1000:]
    
    def record_cache_hit(self):
        """Record cache hit"""
        self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        self.cache_misses += 1
    
    def get_metrics(self) -> ApplicationMetrics:
        """Get current application metrics"""
        # Calculate requests per minute
        now = datetime.utcnow()
        time_diff = (now - self._reset_time).total_seconds() / 60
        requests_per_minute = len(self.request_times) / time_diff if time_diff > 0 else 0
        
        # Calculate cache hit rate
        total_cache_requests = self.cache_hits + self.cache_misses
        cache_hit_rate = (self.cache_hits / total_cache_requests * 100) if total_cache_requests > 0 else 0
        
        return ApplicationMetrics(
            active_users=len(self.active_users),
            requests_per_minute=int(requests_per_minute),
            error_count=self.error_count,
            cache_hit_rate=cache_hit_rate,
            database_connections=0,  # Would need to track this
            response_times=self.request_times.copy()
        )
    
    def reset_metrics(self):
        """Reset metrics (called periodically)"""
        self.request_times.clear()
        self.error_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.active_users.clear()
        self._reset_time = datetime.utcnow()

class HealthChecker:
    """Performs health checks on various system components"""
    
    def __init__(self):
        self.checks = {}
    
    def register_check(self, name: str, check_func, critical: bool = False):
        """Register a health check"""
        self.checks[name] = {
            "func": check_func,
            "critical": critical,
            "last_result": None,
            "last_check": None
        }
    
    async def run_check(self, name: str) -> Dict[str, Any]:
        """Run a specific health check"""
        if name not in self.checks:
            return {"error": f"Check '{name}' not found"}
        
        check = self.checks[name]
        start_time = time.time()
        
        try:
            if asyncio.iscoroutinefunction(check["func"]):
                result = await check["func"]()
            else:
                result = check["func"]()
            
            duration = time.time() - start_time
            
            check_result = {
                "name": name,
                "status": "healthy" if result.get("healthy", True) else "unhealthy",
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat(),
                "details": result,
                "critical": check["critical"]
            }
            
            check["last_result"] = check_result
            check["last_check"] = datetime.utcnow()
            
            return check_result
            
        except Exception as e:
            duration = time.time() - start_time
            
            check_result = {
                "name": name,
                "status": "error",
                "duration": duration,
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "critical": check["critical"]
            }
            
            check["last_result"] = check_result
            check["last_check"] = datetime.utcnow()
            
            logger.error(f"Health check '{name}' failed: {str(e)}")
            return check_result
    
    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all registered health checks"""
        results = {}
        overall_healthy = True
        critical_failures = []
        
        for name in self.checks:
            result = await self.run_check(name)
            results[name] = result
            
            if result["status"] != "healthy":
                overall_healthy = False
                if result.get("critical", False):
                    critical_failures.append(name)
        
        return {
            "overall_status": "healthy" if overall_healthy else "unhealthy",
            "critical_failures": critical_failures,
            "timestamp": datetime.utcnow().isoformat(),
            "checks": results
        }

class MonitoringService:
    """Main monitoring service that coordinates all monitoring activities"""
    
    def __init__(self):
        self.system_monitor = SystemMonitor()
        self.app_monitor = ApplicationMonitor()
        self.health_checker = HealthChecker()
        self._setup_health_checks()
    
    def _setup_health_checks(self):
        """Setup default health checks"""
        # Database health check
        async def check_database():
            try:
                await db_service.get_global_stats()
                return {"healthy": True, "message": "Database accessible"}
            except Exception as e:
                return {"healthy": False, "message": f"Database error: {str(e)}"}
        
        # Memory health check
        def check_memory():
            memory = psutil.virtual_memory()
            if memory.percent > 90:
                return {"healthy": False, "message": f"High memory usage: {memory.percent}%"}
            return {"healthy": True, "message": f"Memory usage: {memory.percent}%"}
        
        # Disk health check
        def check_disk():
            disk = psutil.disk_usage('/')
            if disk.percent > 90:
                return {"healthy": False, "message": f"High disk usage: {disk.percent}%"}
            return {"healthy": True, "message": f"Disk usage: {disk.percent}%"}
        
        self.health_checker.register_check("database", check_database, critical=True)
        self.health_checker.register_check("memory", check_memory, critical=False)
        self.health_checker.register_check("disk", check_disk, critical=False)
    
    async def start(self):
        """Start monitoring service"""
        await self.system_monitor.start_monitoring()
        logger.info("Monitoring service started")
    
    async def stop(self):
        """Stop monitoring service"""
        await self.system_monitor.stop_monitoring()
        logger.info("Monitoring service stopped")
    
    def record_user_request(self, user_id: int, duration: float, success: bool = True):
        """Record user request for monitoring"""
        self.app_monitor.record_request(user_id, duration, success)
    
    def record_cache_operation(self, hit: bool):
        """Record cache operation"""
        if hit:
            self.app_monitor.record_cache_hit()
        else:
            self.app_monitor.record_cache_miss()
    
    async def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status"""
        return await self.health_checker.run_all_checks()
    
    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        try:
            system_metrics = self.system_monitor.get_system_metrics()
            app_metrics = self.app_monitor.get_metrics()
            system_info = self.system_monitor.get_system_info()
            
            # Get database performance stats
            db_stats = await db_service.get_performance_stats(24)
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "system": system_metrics.to_dict(),
                "application": app_metrics.to_dict(),
                "system_info": system_info,
                "database": db_stats,
                "uptime": system_metrics.uptime
            }
            
        except Exception as e:
            logger.error(f"Failed to get performance summary: {str(e)}", exc_info=True)
            return {"error": str(e)}
    
    def format_uptime(self, seconds: float) -> str:
        """Format uptime in human readable format"""
        uptime_delta = timedelta(seconds=int(seconds))
        days = uptime_delta.days
        hours, remainder = divmod(uptime_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
        
        return " ".join(parts)
    
    def format_bytes(self, bytes_value: int) -> str:
        """Format bytes in human readable format"""
        if bytes_value == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB", "TB"]
        i = 0
        while bytes_value >= 1024 and i < len(size_names) - 1:
            bytes_value /= 1024.0
            i += 1
        
        return f"{bytes_value:.2f} {size_names[i]}"

# Global monitoring service instance
monitoring_service = MonitoringService()

# Convenience functions
async def start_monitoring():
    """Start monitoring service"""
    await monitoring_service.start()

async def stop_monitoring():
    """Stop monitoring service"""
    await monitoring_service.stop()

def record_user_request(user_id: int, duration: float, success: bool = True):
    """Record user request"""
    monitoring_service.record_user_request(user_id, duration, success)

def record_cache_operation(hit: bool):
    """Record cache operation"""
    monitoring_service.record_cache_operation(hit)

async def get_health_status():
    """Get health status"""
    return await monitoring_service.get_health_status()

async def get_performance_summary():
    """Get performance summary"""
    return await monitoring_service.get_performance_summary()