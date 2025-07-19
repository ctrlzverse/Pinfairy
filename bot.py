import os, sys, logging, asyncio, re
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
        handle_config,
        handle_leaderboard,
        handle_feedback,
        handle_backup,
        handle_restore
    )
    from handlers.callbacks import handle_button_press
    from core import clean_temp_files, init_db, log_performance_metric, validate_pinterest_url
    from config import BOT_PREFIX
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
    client.add_event_handler(handle_start, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}start$'))
    client.add_event_handler(handle_button_press, events.CallbackQuery())
    client.add_event_handler(handle_help, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}help$'))
    client.add_event_handler(handle_stats, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}stats$'))
    client.add_event_handler(handle_alive, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}alive$'))
    
    # Pinterest commands
    client.add_event_handler(handle_pinterest_photo, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}p(?:\s+(https://.*)|$)'))
    client.add_event_handler(handle_pinterest_video, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}pv(?:\s+(https://.*)|$)'))
    client.add_event_handler(handle_board_link, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}pboard(?:\s+(https://[^\s]+/.*?/.*?/?)|$)'))
    client.add_event_handler(handle_search, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}search(?:\s+(.+)|$)'))
    
    # User management commands
    client.add_event_handler(handle_profile, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}profile$'))
    client.add_event_handler(handle_history, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}history$'))
    client.add_event_handler(handle_quota, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}quota$'))
    client.add_event_handler(handle_config, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}config$'))
    client.add_event_handler(handle_leaderboard, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}leaderboard$'))
    client.add_event_handler(handle_feedback, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}feedback$'))
    client.add_event_handler(handle_backup, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}backup$'))
    client.add_event_handler(handle_restore, events.NewMessage(pattern=rf'^{re.escape(BOT_PREFIX)}restore$'))
    
    logger.info("✅ Semua handler berhasil didaftarkan.")

    # Auto-detect Pinterest link in any message
    @client.on(events.NewMessage(incoming=True))
    async def auto_detect_link(event):
        if not event.text or event.text.startswith(BOT_PREFIX):
            return

        match = re.search(r'(https?://(www\.)?(id\.)?pinterest\.com/[^\s]+|https?://pin\.it/[^\s]+)', event.text)
        if match:
            url = match.group(0).strip()
            from telethon.tl.custom import Button

            validation = validate_pinterest_url(url)
            if not validation["is_valid"]:
                if validation.get("is_dead"):
                    await event.reply(
                        f"⚠️ Link terdeteksi, tapi sepertinya sudah mati atau tidak valid.\n\n`{url}`",
                        buttons=[[Button.inline("🗑️ Tutup", data="close_help")]]
                    )
                return

            buttons = []
            if "/pin/" in url:
                buttons.append([Button.inline("📷 Download Foto", data=f"auto_photo:{url}")])
                buttons.append([Button.inline("🎬 Download Video", data=f"auto_video:{url}")])
            else:
                buttons.append([Button.inline("🗂️ Download Board", data=f"auto_board:{url}")])

            if not buttons:
                return

            buttons.append([Button.inline("🗑️ Tutup", data="close_help")])

            await event.reply(
                f"🔗 Link Pinterest terdeteksi!\n\nPilih aksi untuk:\n`{url}`",
                buttons=buttons
            )
    
    # Schedule background tasks
    async def scheduled_cleanup():
        while True:
            try:
                await clean_temp_files()
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error in cleanup task: {e}")
                await asyncio.sleep(300)

    async def performance_monitor():
        while True:
            try:
                log_performance_metric()
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in performance monitor: {e}")
                await asyncio.sleep(60)

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
