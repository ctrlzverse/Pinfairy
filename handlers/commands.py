import logging
from core import (
    process_start_command,
    process_pinterest_photo,
    process_pinterest_video,
    process_help_command,
    process_stats_command,
    process_alive_command,
    process_search_command  # <-- Impor baru
)

logger = logging.getLogger(__name__)

async def handle_start(event):
    try:
        await process_start_command(event)
    except Exception as e:
        logger.error(f"Error di handle_start: {e}", exc_info=True)

async def handle_pinterest_photo(event):
    try:
        url = event.pattern_match.group(1)
        await process_pinterest_photo(event, url)
    except Exception as e:
        logger.error(f"Error di handle_pinterest_photo: {e}", exc_info=True)

async def handle_pinterest_video(event):
    try:
        url = event.pattern_match.group(1)
        await process_pinterest_video(event, url)
    except Exception as e:
        logger.error(f"Error di handle_pinterest_video: {e}", exc_info=True)

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
        await process_search_command(event, query)
    except Exception as e:
        logger.error(f"Error di handle_search: {e}", exc_info=True)

async def handle_board_link(event):
    from telethon.tl.custom import Button
    try:
        url_match = event.pattern_match.group(1)
        if not url_match: return
        buttons = [
            Button.inline("Kirim sebagai ZIP 📦", data="pboard_zip"), 
            Button.inline("Kirim sebagai Album 🖼️", data="pboard_album")
        ]
        await event.reply("**Board ditemukan!**\n\nBagaimana Anda ingin menerima semua pin?", buttons=buttons)
    except Exception as e:
        logger.error(f"Gagal mengirim pilihan board untuk {url_match}: {e}", exc_info=True)
