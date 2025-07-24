"""
Enhanced command handlers for Pinfairy Bot
Provides optimized handlers with comprehensive error handling, validation, and performance monitoring
"""

import asyncio
import time
import re
from typing import Optional, Dict, Any
from functools import wraps
from telethon.tl.custom import Button
from telethon import events

from core import (
    process_start_command,
    process_pinterest_photo,
    process_pinterest_video,
    process_help_command,
    process_stats_command,
    process_alive_command,
    process_search_command,
    validate_pinterest_url,
    check_rate_limit,
    process_profile_command,
    process_history_command,
    process_quota_command,
    process_config_command,
    update_user_activity,
    log_download,
    check_user_quota,
    process_leaderboard_command,
    process_feedback_command,
    process_backup_command,
    process_restore_command,
    process_contributors_command
)
from exceptions import (
    ErrorHandler, ErrorContext, RateLimitException,
    ValidationException, QuotaExceededException
)
from utils.logger import get_logger
from utils.validators import validate_pinterest_url as validate_url

logger = get_logger(__name__)
error_handler = ErrorHandler(logger)

# Performance tracking
handler_stats = {
    'total_calls': 0,
    'total_time': 0.0,
    'handler_times': {},
    'error_count': 0
}

USAGE_MESSAGES = {
    "photo": "**Cara Penggunaan:**\n`.p <link_foto_pinterest>`\n\nContoh:\n`.p https://pin.it/abcd1234`",
    "video": "**Cara Penggunaan:**\n`.pv <link_video_pinterest>`\n\nContoh:\n`.pv https://pin.it/abcd1234`",
    "board": "**Cara Penggunaan:**\n`.pboard <link_board_pinterest>`\n\nContoh:\n`.pboard https://pinterest.com/username/boardname`\n\nMaksimal 5 board per request.",
    "search": "**Cara Penggunaan:**\n`.search <kata_kunci>`\n\nContoh:\n`.search wallpaper anime`"
}

def handler_wrapper(handler_name: str, require_url: bool = False, check_quota: bool = True):
    """
    Decorator for command handlers with comprehensive error handling and performance monitoring
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(event):
            start_time = time.time()
            context = ErrorContext(
                user_id=event.sender_id,
                username=event.sender.username,
                command=handler_name,
                timestamp=start_time
            )

            try:
                # Update global stats
                handler_stats['total_calls'] += 1

                # Update user activity
                try:
                    username = event.sender.username or event.sender.first_name
                    await update_user_activity(event.sender_id, username)
                except Exception as e:
                    logger.warning(f"Failed to update user activity: {e}")

                # Rate limiting check
                try:
                    rate_limit_result = await check_rate_limit(event.sender_id)
                    if not rate_limit_result['allowed']:
                        raise RateLimitException(
                            f"Rate limit exceeded for user {event.sender_id}",
                            remaining_time=rate_limit_result.get('retry_after', 30),
                            context=context
                        )
                except RateLimitException:
                    raise
                except Exception as e:
                    logger.warning(f"Rate limit check failed: {e}")

                # Quota check
                if check_quota:
                    try:
                        quota_result = await check_user_quota(event.sender_id)
                        if not quota_result['allowed']:
                            raise QuotaExceededException(
                                f"Quota exceeded for user {event.sender_id}",
                                remaining_quota=quota_result.get('remaining', 0),
                                reset_time=quota_result.get('reset_time'),
                                context=context
                            )
                    except QuotaExceededException:
                        raise
                    except Exception as e:
                        logger.warning(f"Quota check failed: {e}")

                # URL validation if required
                if require_url:
                    url = None
                    if hasattr(event, 'pattern_match') and event.pattern_match:
                        url = event.pattern_match.group(1)

                    if not url:
                        raise ValidationException(
                            "URL required but not provided",
                            field="url",
                            context=context
                        )

                    context.url = url

                    # Validate Pinterest URL
                    try:
                        validation_result = await validate_url(url)
                        if not validation_result.get('is_valid', False):
                            raise ValidationException(
                                f"Invalid Pinterest URL: {url}",
                                field="url",
                                context=context
                            )
                    except ValidationException:
                        raise
                    except Exception as e:
                        logger.warning(f"URL validation failed: {e}")

                # Execute the actual handler
                result = await func(event)

                # Update performance stats
                execution_time = time.time() - start_time
                handler_stats['total_time'] += execution_time
                handler_stats['handler_times'][handler_name] = handler_stats['handler_times'].get(handler_name, 0) + execution_time

                logger.debug(f"Handler {handler_name} completed in {execution_time:.3f}s")
                return result

            except Exception as e:
                # Handle all exceptions
                handler_stats['error_count'] += 1
                execution_time = time.time() - start_time

                logger.error(f"Handler {handler_name} failed after {execution_time:.3f}s: {str(e)}")

                # Get user-friendly error message
                user_message = error_handler.handle_exception(e, context)

                # Send error message to user
                try:
                    await event.reply(user_message)
                except Exception as reply_error:
                    logger.error(f"Failed to send error message: {reply_error}")

        return wrapper
    return decorator

@handler_wrapper("start", require_url=False, check_quota=False)
async def handle_start(event):
    """Handle /start command with enhanced error handling"""
    await process_start_command(event)

@handler_wrapper("pinterest_photo", require_url=True, check_quota=True)
async def handle_pinterest_photo(event):
    """Handle Pinterest photo download with comprehensive validation"""
    url = event.pattern_match.group(1).strip()

    # Process the photo download
    await process_pinterest_photo(event, url)

    # Log successful download
    try:
        await log_download(event.sender_id, url, "photo")
    except Exception as e:
        logger.warning(f"Failed to log download: {e}")

async def handle_pinterest_video(event):
    try:
        # Check if URL is provided
        if not event.pattern_match.group(1):
            return await event.edit(USAGE_MESSAGES["video"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])
            
        # Check rate limit
        rate_check = check_rate_limit(event.sender_id)
        if not rate_check["allowed"]:
            return await event.edit(rate_check["message"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])

        # Get and validate URL
        url = event.pattern_match.group(1)
        validation = validate_pinterest_url(url)
        if not validation["is_valid"]:
            return await event.edit(validation["message"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])

        await process_pinterest_video(event, validation["url"])
    except Exception as e:
        logger.error(f"Error di handle_pinterest_video: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat memproses video.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_help(event):
    try:
        await process_help_command(event)
    except Exception as e:
        logger.error(f"Error di handle_help: {e}", exc_info=True)

async def handle_stats(event):
    try:
        await process_stats_command(event)
    except Exception as e:
        logger.error(f"Error di handle_stats: {e}", exc_info=True)

async def handle_alive(event):
    try:
        await process_alive_command(event)
    except Exception as e:
        logger.error(f"Error di handle_alive: {e}", exc_info=True)

async def handle_search(event):
    try:
        query = event.pattern_match.group(1)
        
        # Check if query is provided
        if not query:
            return await event.edit(USAGE_MESSAGES["search"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])
            
        # Check rate limit
        rate_check = check_rate_limit(event.sender_id)
        if not rate_check["allowed"]:
            return await event.edit(rate_check["message"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])
        
        # Validate query
        if len(query.strip()) < 2:
            return await event.edit("⚠️ Query pencarian terlalu pendek. Minimal 2 karakter.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
        
        if len(query) > 100:
            return await event.edit("⚠️ Query pencarian terlalu panjang. Maksimal 100 karakter.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
            
        # Remove potentially harmful characters
        query = re.sub(r'[^\w\s\-]', '', query)
        
        await process_search_command(event, query)
    except Exception as e:
        logger.error(f"Error di handle_search: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat melakukan pencarian.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_board_link(event):
    try:
        # Check if URL is provided
        if not event.pattern_match.group(1):
            return await event.edit(USAGE_MESSAGES["board"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])
            
        # Check rate limit
        rate_check = check_rate_limit(event.sender_id)
        if not rate_check["allowed"]:
            return await event.edit(rate_check["message"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])

        links = event.pattern_match.group(1)
        
        # Ambil semua link dengan regex agar lebih robust
        link_list = re.findall(r'https?://.*?(?=https?://|$)', links)
        if not link_list:
            return await event.edit("Tidak ada link board valid ditemukan.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
        
        # Validate each URL
        valid_links = []
        for link in link_list:
            validation = validate_pinterest_url(link.strip())
            if validation["is_valid"]:
                valid_links.append(validation["url"])
        
        if not valid_links:
            return await event.edit("Tidak ada link Pinterest board yang valid ditemukan.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
        
        # Limit number of boards to prevent abuse
        if len(valid_links) > 5:
            return await event.edit("⚠️ Maksimal 5 board per request untuk mencegah overload server.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
        
        buttons = [
            Button.inline("Kirim sebagai ZIP 📦", data="pboard_zip"),
            Button.inline("Kirim sebagai Album 🖼️", data="pboard_album")
        ]
        await event.edit(f"**Board Download**\n\nDitemukan {len(valid_links)} link board valid. Pilih mode pengiriman:", buttons=buttons)
    except Exception as e:
        logger.error(f"Gagal mengirim pilihan board: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat memproses board.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_profile(event):
    """Handle .profile command."""
    try:
        await process_profile_command(event)
    except Exception as e:
        logger.error(f"Error di handle_profile: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat mengambil profil.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_history(event):
    """Handle .history command."""
    try:
        await process_history_command(event)
    except Exception as e:
        logger.error(f"Error di handle_history: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat mengambil riwayat.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_quota(event):
    """Handle .quota command."""
    try:
        await process_quota_command(event)
    except Exception as e:
        logger.error(f"Error di handle_quota: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat mengecek quota.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_config(event):
    """Handle .config command."""
    try:
        await process_config_command(event)
    except Exception as e:
        logger.error(f"Error di handle_config: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat mengakses konfigurasi.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_leaderboard(event):
    """Handle .leaderboard command."""
    try:
        await process_leaderboard_command(event)
    except Exception as e:
        logger.error(f"Error di handle_leaderboard: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat mengambil leaderboard.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_feedback(event):
    """Handle .feedback command."""
    try:
        await process_feedback_command(event)
    except Exception as e:
        logger.error(f"Error di handle_feedback: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat mengirim feedback.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_backup(event):
    """Handle .backup command."""
    try:
        await process_backup_command(event)
    except Exception as e:
        logger.error(f"Error di handle_backup: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat melakukan backup.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

async def handle_restore(event):
    """Handle .restore command."""
    try:
        await process_restore_command(event)
    except Exception as e:
        logger.error(f"Error di handle_restore: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat melakukan restore.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
