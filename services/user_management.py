"""
User management service for Pinfairy Bot
Handles user operations, quota management, and rate limiting
"""

import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from constants import (
    DEFAULT_DAILY_QUOTA, DEFAULT_USER_SETTINGS, RATE_LIMIT_SECONDS,
    ERROR_CODES, SUCCESS_CODES
)
from exceptions import RateLimitException, QuotaExceededException, DatabaseException
from utils.logger import get_logger
from services.database import db_service

logger = get_logger(__name__)

class RateLimiter:
    """In-memory rate limiter for user requests"""
    
    def __init__(self):
        self._user_requests = {}
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.time()
    
    def _cleanup_old_entries(self):
        """Remove old rate limit entries"""
        current_time = time.time()
        if current_time - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff_time = current_time - (RATE_LIMIT_SECONDS * 2)
        self._user_requests = {
            user_id: timestamp 
            for user_id, timestamp in self._user_requests.items()
            if timestamp > cutoff_time
        }
        self._last_cleanup = current_time
    
    def check_rate_limit(self, user_id: int) -> Dict[str, Any]:
        """Check if user is rate limited"""
        self._cleanup_old_entries()
        
        current_time = time.time()
        
        if user_id in self._user_requests:
            time_diff = current_time - self._user_requests[user_id]
            if time_diff < RATE_LIMIT_SECONDS:
                remaining = RATE_LIMIT_SECONDS - time_diff
                return {
                    "allowed": False,
                    "remaining_time": remaining,
                    "message": f"⏳ Tunggu {remaining:.1f} detik sebelum request berikutnya."
                }
        
        self._user_requests[user_id] = current_time
        return {"allowed": True}

class UserService:
    """Service for managing user operations"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter()
    
    async def create_or_update_user(self, user_id: int, username: str = None,
                                  first_name: str = None, last_name: str = None) -> Dict[str, Any]:
        """Create new user or update existing user info"""
        try:
            # Check if user exists
            existing_user = await db_service.get_user_profile(user_id)
            
            if existing_user:
                # Update existing user
                await db_service.update_user_activity(user_id, username, first_name, last_name)
                logger.info(f"Updated user activity for {user_id}")
                return {"action": "updated", "user": existing_user}
            else:
                # Create new user
                await db_service.create_user(user_id, username, first_name, last_name)
                new_user = await db_service.get_user_profile(user_id)
                logger.info(f"Created new user {user_id}")
                return {"action": "created", "user": new_user}
                
        except Exception as e:
            logger.error(f"Failed to create/update user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"User operation failed: {str(e)}")
    
    async def get_user_profile(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Get comprehensive user profile"""
        try:
            profile = await db_service.get_user_profile(user_id)
            if not profile:
                return None
            
            # Add computed fields
            quota_info = await self.check_user_quota(user_id)
            profile.update({
                "quota_status": quota_info,
                "display_name": profile.get("first_name") or profile.get("username") or f"User{user_id}",
                "is_new_user": (datetime.utcnow() - datetime.fromisoformat(profile["first_seen"])).days < 1
            })
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to get user profile for {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to get user profile: {str(e)}")
    
    async def update_user_settings(self, user_id: int, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Update user settings with validation"""
        try:
            from utils.validators import InputValidator
            
            # Validate settings
            validation_result = InputValidator.validate_user_settings(settings)
            if not validation_result["valid"]:
                return {
                    "success": False,
                    "errors": validation_result["errors"]
                }
            
            # Update in database
            await db_service.update_user_settings(user_id, validation_result["settings"])
            
            # Get updated profile
            updated_profile = await self.get_user_profile(user_id)
            
            logger.info(f"Updated settings for user {user_id}", user_id=user_id)
            
            return {
                "success": True,
                "settings": updated_profile["settings"] if updated_profile else {},
                "message": "Pengaturan berhasil diperbarui!"
            }
            
        except Exception as e:
            logger.error(f"Failed to update settings for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to update settings: {str(e)}")
    
    def check_rate_limit(self, user_id: int) -> Dict[str, Any]:
        """Check rate limit for user"""
        return self.rate_limiter.check_rate_limit(user_id)
    
    async def check_user_quota(self, user_id: int) -> Dict[str, Any]:
        """Check user's daily quota with automatic reset"""
        try:
            return await db_service.check_user_quota(user_id)
        except Exception as e:
            logger.error(f"Failed to check quota for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to check quota: {str(e)}")
    
    async def log_user_download(self, user_id: int, media_type: str, url: str,
                               success: bool, **kwargs) -> Dict[str, Any]:
        """Log user download with quota and rate limit checks"""
        try:
            # Check rate limit
            rate_check = self.check_rate_limit(user_id)
            if not rate_check["allowed"]:
                raise RateLimitException(
                    rate_check["message"], 
                    ERROR_CODES["RATE_LIMITED"]
                )
            
            # Check quota before successful download
            if success:
                quota_check = await self.check_user_quota(user_id)
                if not quota_check["allowed"]:
                    if quota_check.get("is_banned"):
                        raise QuotaExceededException(
                            f"Akun Anda telah dibanned: {quota_check.get('ban_reason', 'Tidak ada alasan')}",
                            ERROR_CODES["QUOTA_EXCEEDED"]
                        )
                    else:
                        raise QuotaExceededException(
                            f"Quota harian habis. Sisa: {quota_check['remaining']}",
                            ERROR_CODES["QUOTA_EXCEEDED"]
                        )
            
            # Log the download
            await db_service.log_download(
                user_id=user_id,
                media_type=media_type,
                url=url,
                success=success,
                **kwargs
            )
            
            # Update user activity
            await db_service.update_user_activity(user_id)
            
            result = {"success": True, "logged": True}
            
            if success:
                # Get updated quota info
                updated_quota = await self.check_user_quota(user_id)
                result["quota_remaining"] = updated_quota["remaining"]
                
                logger.log_user_action(
                    user_id=user_id,
                    action=f"download_{media_type}",
                    url=url,
                    success=True
                )
            
            return result
            
        except (RateLimitException, QuotaExceededException):
            # Re-raise these specific exceptions
            raise
        except Exception as e:
            logger.error(f"Failed to log download for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to log download: {str(e)}")
    
    async def get_user_download_history(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get user's download history with enhanced formatting"""
        try:
            history = await db_service.get_download_history(user_id, limit)
            
            # Enhance history with additional info
            for item in history:
                item["formatted_timestamp"] = self._format_timestamp(item["timestamp"])
                item["status_emoji"] = "✅" if item["success"] else "❌"
                item["media_type_emoji"] = self._get_media_emoji(item["media_type"])
                
                if item["file_size"]:
                    item["formatted_size"] = self._format_file_size(item["file_size"])
                
                if item["duration"]:
                    item["formatted_duration"] = f"{item['duration']:.2f}s"
            
            return history
            
        except Exception as e:
            logger.error(f"Failed to get download history for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to get download history: {str(e)}")
    
    async def get_user_statistics(self, user_id: int) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        try:
            profile = await self.get_user_profile(user_id)
            if not profile:
                return {"error": "User not found"}
            
            # Get download history for analysis
            history = await db_service.get_download_history(user_id, 100)
            
            # Calculate statistics
            total_downloads = profile["total_downloads"]
            successful_downloads = sum(1 for h in history if h["success"])
            failed_downloads = len(history) - successful_downloads
            success_rate = (successful_downloads / len(history) * 100) if history else 0
            
            # Media type breakdown
            media_breakdown = {}
            for h in history:
                if h["success"]:
                    media_breakdown[h["media_type"]] = media_breakdown.get(h["media_type"], 0) + 1
            
            # Average download time
            successful_with_duration = [h for h in history if h["success"] and h["duration"]]
            avg_duration = (
                sum(h["duration"] for h in successful_with_duration) / len(successful_with_duration)
                if successful_with_duration else 0
            )
            
            return {
                "user_id": user_id,
                "total_downloads": total_downloads,
                "successful_downloads": successful_downloads,
                "failed_downloads": failed_downloads,
                "success_rate": round(success_rate, 1),
                "media_breakdown": media_breakdown,
                "average_duration": round(avg_duration, 2),
                "days_active": (datetime.utcnow() - datetime.fromisoformat(profile["first_seen"])).days,
                "quota_status": profile["quota_status"]
            }
            
        except Exception as e:
            logger.error(f"Failed to get statistics for user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to get user statistics: {str(e)}")
    
    def _format_timestamp(self, timestamp: str) -> str:
        """Format timestamp for display"""
        try:
            dt = datetime.fromisoformat(timestamp)
            now = datetime.utcnow()
            diff = now - dt
            
            if diff.days > 0:
                return f"{diff.days} hari lalu"
            elif diff.seconds > 3600:
                hours = diff.seconds // 3600
                return f"{hours} jam lalu"
            elif diff.seconds > 60:
                minutes = diff.seconds // 60
                return f"{minutes} menit lalu"
            else:
                return "Baru saja"
        except:
            return timestamp[:16]  # Fallback to simple format
    
    def _get_media_emoji(self, media_type: str) -> str:
        """Get emoji for media type"""
        emoji_map = {
            "photo": "🖼️",
            "video": "🎬",
            "board": "🗂️"
        }
        return emoji_map.get(media_type, "📄")
    
    def _format_file_size(self, size_bytes: int) -> str:
        """Format file size for display"""
        if size_bytes == 0:
            return "0 B"
        
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        
        return f"{size_bytes:.1f} {size_names[i]}"

class AdminService:
    """Service for admin operations"""
    
    def __init__(self):
        self.user_service = UserService()
    
    async def ban_user(self, admin_id: int, user_id: int, reason: str) -> Dict[str, Any]:
        """Ban a user"""
        try:
            await db_service.ban_user(admin_id, user_id, reason)
            
            logger.info(f"Admin {admin_id} banned user {user_id}: {reason}",
                       user_id=admin_id, action="ban_user", target_user_id=user_id)
            
            return {
                "success": True,
                "message": f"User {user_id} telah dibanned",
                "reason": reason
            }
            
        except Exception as e:
            logger.error(f"Failed to ban user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to ban user: {str(e)}")
    
    async def unban_user(self, admin_id: int, user_id: int) -> Dict[str, Any]:
        """Unban a user"""
        try:
            await db_service.unban_user(admin_id, user_id)
            
            logger.info(f"Admin {admin_id} unbanned user {user_id}",
                       user_id=admin_id, action="unban_user", target_user_id=user_id)
            
            return {
                "success": True,
                "message": f"User {user_id} telah di-unban"
            }
            
        except Exception as e:
            logger.error(f"Failed to unban user {user_id}: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to unban user: {str(e)}")
    
    async def get_user_list(self, limit: int = 50, banned_only: bool = False) -> List[Dict[str, Any]]:
        """Get list of users for admin"""
        try:
            # This would need to be implemented in database service
            # For now, return empty list
            return []
            
        except Exception as e:
            logger.error(f"Failed to get user list: {str(e)}", exc_info=True)
            raise DatabaseException(f"Failed to get user list: {str(e)}")

# Global service instances
user_service = UserService()
admin_service = AdminService()

# Convenience functions for backward compatibility
async def create_or_update_user(user_id: int, username: str = None, **kwargs):
    """Create or update user"""
    return await user_service.create_or_update_user(user_id, username, **kwargs)

async def check_user_quota(user_id: int):
    """Check user quota"""
    return await user_service.check_user_quota(user_id)

def check_rate_limit(user_id: int):
    """Check rate limit"""
    return user_service.check_rate_limit(user_id)

async def log_user_download(user_id: int, media_type: str, url: str, success: bool, **kwargs):
    """Log user download"""
    return await user_service.log_user_download(user_id, media_type, url, success, **kwargs)