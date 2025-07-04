import os, sys, logging, asyncio
from telethon import TelegramClient, events
from dotenv import load_dotenv

try:
    from handlers.commands import (
        handle_start, 
        handle_pinterest_photo, 
        handle_pinterest_video,
        handle_help,
        handle_stats,
        handle_board_link,
        handle_alive,
        handle_search,
        handle_profile,
        handle_history,
        handle_quota,
        handle_config
    )
    from handlers.callbacks import handle_button_press
    from core import clean_temp_files, init_db, log_performance_metric
except ImportError as e:
    print(f"❌ Gagal mengimpor handler: {e}"); sys.exit(1)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s', datefmt='%d-%b-%y %H:%M:%S')
logger = logging.getLogger(__name__)
load_dotenv()
API_ID = os.getenv("API_ID"); API_HASH = os.getenv("API_HASH"); BOT_TOKEN = os.getenv("BOT_TOKEN")
if not all([API_ID, API_HASH, BOT_TOKEN]): logger.critical("❌ Kredensial tidak lengkap!"); sys.exit(1)
API_ID = int(API_ID)
client = TelegramClient('bot_session', API_ID, API_HASH)

async def main():
    """Menyatukan semua logika startup dan menjalankan bot."""
    
    await client.start(bot_token=BOT_TOKEN)
    logger.info("Bot berhasil terhubung.")
    
    init_db()
    logger.info("Mendaftarkan semua event handler...")
    
    # Core commands
    client.add_event_handler(handle_start, events.NewMessage(pattern=r'^[./]start$'))
    client.add_event_handler(handle_button_press, events.CallbackQuery())
    client.add_event_handler(handle_help, events.NewMessage(pattern=r'^\.help$'))
    client.add_event_handler(handle_stats, events.NewMessage(pattern=r'^\.stats$'))
    client.add_event_handler(handle_alive, events.NewMessage(pattern=r'^\.alive$'))
    
    # Pinterest commands
    client.add_event_handler(handle_pinterest_photo, events.NewMessage(pattern=r'^\.p(?:\s+(https://.*)|$)'))
    client.add_event_handler(handle_pinterest_video, events.NewMessage(pattern=r'^\.pv(?:\s+(https://.*)|$)'))
    client.add_event_handler(handle_board_link, events.NewMessage(pattern=r'^\.pboard(?:\s+(https://[^\s]+/.*?/.*?/?)|$)'))
    client.add_event_handler(handle_search, events.NewMessage(pattern=r'^\.search(?:\s+(.+)|$)'))
    
    # User management commands
    client.add_event_handler(handle_profile, events.NewMessage(pattern=r'^\.profile$'))
    client.add_event_handler(handle_history, events.NewMessage(pattern=r'^\.history$'))
    client.add_event_handler(handle_quota, events.NewMessage(pattern=r'^\.quota$'))
    client.add_event_handler(handle_config, events.NewMessage(pattern=r'^\.config$'))
    
    logger.info("✅ Semua handler berhasil didaftarkan.")
    
    # Schedule background tasks
    async def scheduled_cleanup():
        """Scheduled task for cleaning temporary files."""
        while True:
            try:
                await clean_temp_files()
                await asyncio.sleep(3600)  # Every hour
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error

    async def performance_monitor():
        """Scheduled task for monitoring system performance."""
        while True:
            try:
                log_performance_metric()
                await asyncio.sleep(300)  # Every 5 minutes
            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")
                await asyncio.sleep(60)  # Wait 1 minute on error

    # Start background tasks
    asyncio.create_task(scheduled_cleanup())
    asyncio.create_task(performance_monitor())
    
    logger.info("🧹 Layanan pembersih cache dan monitor performa telah dijadwalkan.")
    logger.info("🚀 Bot sekarang online!")
    
    await client.run_until_disconnected()

if __name__ == '__main__':
    logger.info("Memulai bot...")
    try:
        client.loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.warning("Perintah berhenti (Ctrl+C) diterima.")
    except Exception as e:
        logger.critical(f"❌ Terjadi kesalahan fatal: {e}", exc_info=True)
    finally:
        if client.is_connected():
            client.disconnect()
        logger.info("🛑 Bot telah berhenti.")