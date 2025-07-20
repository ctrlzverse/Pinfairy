import logging
import re
from telethon.tl.custom import Button
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

logger = logging.getLogger(__name__)

USAGE_MESSAGES = {
    "photo": "**Cara Penggunaan:**\n`.p <link_foto_pinterest>`\n\nContoh:\n`.p https://pin.it/abcd1234`",
    "video": "**Cara Penggunaan:**\n`.pv <link_video_pinterest>`\n\nContoh:\n`.pv https://pin.it/abcd1234`",
    "board": "**Cara Penggunaan:**\n`.pboard <link_board_pinterest>`\n\nContoh:\n`.pboard https://pinterest.com/username/boardname`\n\nMaksimal 5 board per request.",
    "search": "**Cara Penggunaan:**\n`.search <kata_kunci>`\n\nContoh:\n`.search wallpaper anime`"
}

async def handle_start(event):
    try:
        await process_start_command(event)
    except Exception as e:
        logger.error(f"Error di handle_start: {e}", exc_info=True)

async def handle_pinterest_photo(event):
    try:
        # Update user activity
        username = event.sender.username or event.sender.first_name
        update_user_activity(event.sender_id, username)
        
        # Check if URL is provided
        if not event.pattern_match.group(1):
            return await event.edit(USAGE_MESSAGES["photo"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])
            
        # Check quota
        quota_check = check_user_quota(event.sender_id)
        if not quota_check["allowed"]:
            return await event.edit(f"⚠️ Quota harian Anda sudah habis. Sisa: {quota_check['remaining']}", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
            
        # Check rate limit
        rate_check = check_rate_limit(event.sender_id)
        if not rate_check["allowed"]:
            return await event.edit(rate_check["message"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])

        # Get and validate URL
        url = event.pattern_match.group(1)
        validation = validate_pinterest_url(url)
        if not validation["is_valid"]:
            log_download(event.sender_id, "photo", url, False, validation["message"])
            return await event.edit(validation["message"], buttons=[Button.inline("🗑️ Tutup", data="close_help")])

        try:
            await process_pinterest_photo(event, validation["url"])
            log_download(event.sender_id, "photo", validation["url"], True)
        except Exception as download_error:
            log_download(event.sender_id, "photo", validation["url"], False, str(download_error))
            raise download_error
            
    except Exception as e:
        logger.error(f"Error di handle_pinterest_photo: {e}", exc_info=True)
        await event.edit("❌ Terjadi kesalahan saat memproses foto.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])

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
