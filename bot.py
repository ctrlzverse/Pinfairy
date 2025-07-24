"""
Pinfairy Bot - Telegram bot for downloading Pinterest media
Enhanced version with service-based architecture and improved error handling
"""

import asyncio
import sys
import signal
import os
import re
from typing import Optional

from telethon import TelegramClient, events
from dotenv import load_dotenv

# Load environment variables first
load_dotenv()

# Import services and utilities with fallback to basic functionality
try:
    from services.config_manager import load_config, get_config
    from services.database import init_db
    from services.monitoring import start_monitoring, stop_monitoring
    from utils.logger import get_logger
    from exceptions import ConfigurationException
    ENHANCED_MODE = True
    logger = get_logger(__name__)
except ImportError as e:
    # Fallback to basic logging if enhanced services not available
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - [%(levelname)s] - %(message)s',
        datefmt='%d-%b-%y %H:%M:%S'
    )
    logger = logging.getLogger(__name__)
    logger.warning(f"Enhanced services not available, using basic mode: {e}")
    ENHANCED_MODE = False

# Import handlers
try:
    from handlers.commands import (
        handle_start, handle_pinterest_photo, handle_pinterest_video,
        handle_help, handle_stats, handle_board_link, handle_alive,
        handle_search, handle_profile, handle_history, handle_quota,
        handle_config, handle_leaderboard, handle_feedback,
        handle_backup, handle_restore
    )
    from handlers.callbacks import handle_button_press
except ImportError as e:
    logger.critical(f"❌ Failed to import handlers: {e}")
    sys.exit(1)

# Import core functions with fallback
try:
    if ENHANCED_MODE:
        from core import clean_temp_files, log_performance_metric, validate_pinterest_url
    else:
        from core import clean_temp_files, init_db, log_performance_metric, validate_pinterest_url
        from config import BOT_PREFIX
except ImportError as e:
    logger.critical(f"❌ Failed to import core functions: {e}")
    sys.exit(1)

class PinfairyBot:
    """Main bot class with enhanced lifecycle management"""

    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.config = None
        self._running = False
        self._shutdown_event = asyncio.Event()

    async def initialize(self):
        """Initialize bot with all services"""
        try:
            logger.info("🚀 Starting Pinfairy Bot initialization...")

            # Load configuration
            if ENHANCED_MODE:
                logger.info("📋 Loading configuration...")
                self.config = load_config()
                logger.info("✅ Configuration loaded successfully")

                # Validate startup requirements
                from services.config_manager import config_manager
                validation = config_manager.validate_startup_requirements()

                if not validation["valid"]:
                    for issue in validation["issues"]:
                        logger.error(f"❌ {issue}")
                    raise ConfigurationException("Startup validation failed")

                if validation["warnings"]:
                    for warning in validation["warnings"]:
                        logger.warning(f"⚠️ {warning}")
            else:
                # Basic configuration from environment
                API_ID = os.getenv("API_ID")
                API_HASH = os.getenv("API_HASH")
                BOT_TOKEN = os.getenv("BOT_TOKEN")

                if not all([API_ID, API_HASH, BOT_TOKEN]):
                    logger.critical("❌ Kredensial tidak lengkap!")
                    sys.exit(1)

                # Create basic config object
                class BasicConfig:
                    def __init__(self):
                        self.api_id = int(API_ID)
                        self.api_hash = API_HASH
                        self.bot_token = BOT_TOKEN
                        self.bot_prefix = os.getenv("BOT_PREFIX", "/")

                self.config = BasicConfig()

            # Initialize Telegram client
            logger.info("📱 Initializing Telegram client...")
            self.client = TelegramClient(
                'bot_session',
                self.config.api_id,
                self.config.api_hash
            )

            # Start Telegram client
            await self.client.start(bot_token=self.config.bot_token)
            logger.info("✅ Telegram client connected")

            # Initialize database
            logger.info("🗄️ Initializing database...")
            if ENHANCED_MODE:
                await init_db()
            else:
                init_db()
            logger.info("✅ Database initialized")

            # Start monitoring if available
            if ENHANCED_MODE:
                logger.info("📊 Starting monitoring services...")
                await start_monitoring()
                logger.info("✅ Monitoring services started")

            # Register event handlers
            logger.info("🔧 Registering event handlers...")
            self._register_handlers()
            logger.info("✅ Event handlers registered")

            # Setup auto-detection
            self._setup_auto_detection()

            # Setup background tasks
            self._setup_background_tasks()

            logger.info("🎉 Pinfairy Bot initialized successfully!")

        except Exception as e:
            logger.critical(f"❌ Failed to initialize bot: {str(e)}", exc_info=True)
            raise

    def _register_handlers(self):
        """Register all event handlers"""
        prefix = re.escape(self.config.bot_prefix)

        # Core commands
        self.client.add_event_handler(
            handle_start,
            events.NewMessage(pattern=rf'^{prefix}start$')
        )
        self.client.add_event_handler(handle_button_press, events.CallbackQuery())
        self.client.add_event_handler(
            handle_help,
            events.NewMessage(pattern=rf'^{prefix}help$')
        )
        self.client.add_event_handler(
            handle_stats,
            events.NewMessage(pattern=rf'^{prefix}stats$')
        )
        self.client.add_event_handler(
            handle_alive,
            events.NewMessage(pattern=rf'^{prefix}alive$')
        )

        # Pinterest commands
        self.client.add_event_handler(
            handle_pinterest_photo,
            events.NewMessage(pattern=rf'^{prefix}p(?:\s+(https://.*)|$)')
        )
        self.client.add_event_handler(
            handle_pinterest_video,
            events.NewMessage(pattern=rf'^{prefix}pv(?:\s+(https://.*)|$)')
        )
        self.client.add_event_handler(
            handle_board_link,
            events.NewMessage(pattern=rf'^{prefix}pboard(?:\s+(https://[^\s]+/.*?/.*?/?)|$)')
        )
        self.client.add_event_handler(
            handle_search,
            events.NewMessage(pattern=rf'^{prefix}search(?:\s+(.+)|$)')
        )

        # User management commands
        self.client.add_event_handler(
            handle_profile,
            events.NewMessage(pattern=rf'^{prefix}profile$')
        )
        self.client.add_event_handler(
            handle_history,
            events.NewMessage(pattern=rf'^{prefix}history$')
        )
        self.client.add_event_handler(
            handle_quota,
            events.NewMessage(pattern=rf'^{prefix}quota$')
        )
        self.client.add_event_handler(
            handle_config,
            events.NewMessage(pattern=rf'^{prefix}config$')
        )
        self.client.add_event_handler(
            handle_leaderboard,
            events.NewMessage(pattern=rf'^{prefix}leaderboard$')
        )
        self.client.add_event_handler(
            handle_feedback,
            events.NewMessage(pattern=rf'^{prefix}feedback$')
        )
        self.client.add_event_handler(
            handle_backup,
            events.NewMessage(pattern=rf'^{prefix}backup$')
        )
        self.client.add_event_handler(
            handle_restore,
            events.NewMessage(pattern=rf'^{prefix}restore$')
        )

    def _setup_auto_detection(self):
        """Setup auto-detection for Pinterest links"""
        @self.client.on(events.NewMessage(incoming=True))
        async def auto_detect_link(event):
            if not event.text or event.text.startswith(self.config.bot_prefix):
                return

            match = re.search(
                r'(https?://(www\.)?(id\.)?pinterest\.com/[^\s]+|https?://pin\.it/[^\s]+)',
                event.text
            )
            if match:
                url = match.group(0).strip()
                from telethon.tl.custom import Button

                try:
                    if ENHANCED_MODE:
                        validation = await validate_pinterest_url(url)
                    else:
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
                except Exception as e:
                    logger.error(f"Error in auto-detection: {e}")

    def _setup_background_tasks(self):
        """Setup background tasks"""
        async def scheduled_cleanup():
            while True:
                try:
                    await clean_temp_files()
                    await asyncio.sleep(3600)  # Run every hour
                except Exception as e:
                    logger.error(f"Error in cleanup task: {e}")
                    await asyncio.sleep(300)  # Retry after 5 minutes

        async def performance_monitor():
            while True:
                try:
                    if ENHANCED_MODE:
                        await log_performance_metric("system_health", {"status": "running"})
                    await asyncio.sleep(300)  # Run every 5 minutes
                except Exception as e:
                    logger.error(f"Error in performance monitor: {e}")
                    await asyncio.sleep(60)  # Retry after 1 minute

        # Start background tasks
        asyncio.create_task(scheduled_cleanup())
        if ENHANCED_MODE:
            asyncio.create_task(performance_monitor())

    async def run(self):
        """Run the bot"""
        try:
            self._running = True
            logger.info("🚀 Bot is now online!")

            # Setup signal handlers for graceful shutdown
            def signal_handler(signum, frame):
                logger.info(f"Received signal {signum}, initiating shutdown...")
                asyncio.create_task(self.shutdown())

            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)

            # Run until shutdown
            await self.client.run_until_disconnected()

        except Exception as e:
            logger.error(f"Error running bot: {e}", exc_info=True)
            raise

    async def shutdown(self):
        """Graceful shutdown"""
        if not self._running:
            return

        logger.info("🛑 Initiating graceful shutdown...")
        self._running = False

        try:
            # Stop monitoring if available
            if ENHANCED_MODE:
                logger.info("📊 Stopping monitoring services...")
                await stop_monitoring()

            # Disconnect client
            if self.client and self.client.is_connected():
                logger.info("📱 Disconnecting Telegram client...")
                await self.client.disconnect()

            # Set shutdown event
            self._shutdown_event.set()

            logger.info("✅ Shutdown completed successfully")

        except Exception as e:
            logger.error(f"Error during shutdown: {e}", exc_info=True)


async def main():
    """Main entry point"""
    bot = PinfairyBot()

    try:
        await bot.initialize()
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        await bot.shutdown()


if __name__ == '__main__':
    logger.info("🚀 Starting Pinfairy Bot...")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Shutdown signal received (Ctrl+C)")
    except Exception as e:
        logger.critical(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("🛑 Bot has stopped.")
