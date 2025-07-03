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
        handle_search
    )
    from handlers.callbacks import handle_button_press
    from core import clean_temp_files, init_db
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
    
    client.add_event_handler(handle_start, events.NewMessage(pattern=r'^[./]start$'))
    client.add_event_handler(handle_button_press, events.CallbackQuery())
    client.add_event_handler(handle_pinterest_photo, events.NewMessage(pattern=r'^\.p\s+(https://.*)'))
    client.add_event_handler(handle_pinterest_video, events.NewMessage(pattern=r'^\.pv\s+(https://.*)'))
    client.add_event_handler(handle_board_link, events.NewMessage(pattern=r'^\.pboard\s+(https://[^\s]+/.*?/.*?/?)'))
    client.add_event_handler(handle_help, events.NewMessage(pattern=r'^\.help$'))
    client.add_event_handler(handle_stats, events.NewMessage(pattern=r'^\.stats$'))
    client.add_event_handler(handle_alive, events.NewMessage(pattern=r'^\.alive$'))
    client.add_event_handler(handle_search, events.NewMessage(pattern=r'^\.search\s+(.+)'))
    
    logger.info("✅ Semua handler berhasil didaftarkan.")
    
    async def scheduled_cleanup():
        while True: await clean_temp_files(); await asyncio.sleep(3600)

    asyncio.create_task(scheduled_cleanup())
    logger.info("🧹 Layanan pembersih cache otomatis telah dijadwalkan.")
    
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