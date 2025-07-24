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
    """Main bot class with enhanced lifecycle management and performance monitoring"""

    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self.config = None
        self._running = False
        self._shutdown_event = asyncio.Event()
        self._background_tasks: set = set()
        self._performance_metrics = {
            'start_time': None,
            'messages_processed': 0,
            'errors_count': 0,
            'last_error_time': None
        }
        self._health_check_interval = 60  # seconds

    async def initialize(self):
        """Initialize bot with all services and comprehensive error handling"""
        initialization_start = time.time()

        try:
            logger.info("🚀 Starting Pinfairy Bot initialization...")
            self._performance_metrics['start_time'] = initialization_start

            # Load configuration with timeout
            config_start = time.time()
            if ENHANCED_MODE:
                logger.info("📋 Loading enhanced configuration...")
                try:
                    self.config = load_config()
                    logger.info(f"✅ Configuration loaded in {time.time() - config_start:.2f}s")

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

                except Exception as e:
                    logger.error(f"Enhanced configuration failed: {e}, falling back to basic mode")
                    ENHANCED_MODE = False

            if not ENHANCED_MODE:
                logger.info("📋 Loading basic configuration...")
                # Basic configuration from environment
                API_ID = os.getenv("API_ID")
                API_HASH = os.getenv("API_HASH")
                BOT_TOKEN = os.getenv("BOT_TOKEN")

                if not all([API_ID, API_HASH, BOT_TOKEN]):
                    logger.critical("❌ Missing required credentials!")
                    raise ConfigurationException("Missing API_ID, API_HASH, or BOT_TOKEN")

                # Create basic config object
                class BasicConfig:
                    def __init__(self):
                        self.api_id = int(API_ID)
                        self.api_hash = API_HASH
                        self.bot_token = BOT_TOKEN
                        self.bot_prefix = os.getenv("BOT_PREFIX", "/")

                self.config = BasicConfig()
                logger.info(f"✅ Basic configuration loaded in {time.time() - config_start:.2f}s")

            # Initialize Telegram client with retry logic
            client_start = time.time()
            logger.info("📱 Initializing Telegram client...")

            max_client_retries = 3
            for attempt in range(max_client_retries):
                try:
                    self.client = TelegramClient(
                        'bot_session',
                        self.config.api_id,
                        self.config.api_hash,
                        connection_retries=5,
                        retry_delay=1,
                        timeout=30
                    )

                    # Start Telegram client with timeout
                    await asyncio.wait_for(
                        self.client.start(bot_token=self.config.bot_token),
                        timeout=30.0
                    )

                    logger.info(f"✅ Telegram client connected in {time.time() - client_start:.2f}s")
                    break

                except asyncio.TimeoutError:
                    logger.warning(f"Telegram client connection timeout (attempt {attempt + 1}/{max_client_retries})")
                    if attempt == max_client_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

                except Exception as e:
                    logger.error(f"Telegram client connection failed (attempt {attempt + 1}/{max_client_retries}): {e}")
                    if attempt == max_client_retries - 1:
                        raise
                    await asyncio.sleep(2 ** attempt)

            # Initialize database with retry logic
            db_start = time.time()
            logger.info("🗄️ Initializing database...")

            max_db_retries = 3
            for attempt in range(max_db_retries):
                try:
                    if ENHANCED_MODE:
                        await init_db()
                    else:
                        init_db()
                    logger.info(f"✅ Database initialized in {time.time() - db_start:.2f}s")
                    break
                except Exception as e:
                    logger.warning(f"Database initialization failed (attempt {attempt + 1}/{max_db_retries}): {e}")
                    if attempt == max_db_retries - 1:
                        raise
                    await asyncio.sleep(1)

            # Start monitoring if available
            if ENHANCED_MODE:
                monitoring_start = time.time()
                logger.info("📊 Starting monitoring services...")
                try:
                    await start_monitoring()
                    logger.info(f"✅ Monitoring services started in {time.time() - monitoring_start:.2f}s")
                except Exception as e:
                    logger.warning(f"Monitoring services failed to start: {e}")
                    # Continue without monitoring

            # Register event handlers with error handling
            handlers_start = time.time()
            logger.info("🔧 Registering event handlers...")
            try:
                self._register_handlers()
                logger.info(f"✅ Event handlers registered in {time.time() - handlers_start:.2f}s")
            except Exception as e:
                logger.error(f"Failed to register handlers: {e}")
                raise

            # Setup auto-detection with error handling
            try:
                self._setup_auto_detection()
                logger.info("✅ Auto-detection configured")
            except Exception as e:
                logger.warning(f"Auto-detection setup failed: {e}")

            # Setup background tasks with error handling
            try:
                self._setup_background_tasks()
                logger.info("✅ Background tasks configured")
            except Exception as e:
                logger.warning(f"Background tasks setup failed: {e}")

            # Log initialization summary
            total_time = time.time() - initialization_start
            logger.info(f"🎉 Pinfairy Bot initialized successfully in {total_time:.2f}s")

            # Start health monitoring
            self._start_health_monitoring()

        except Exception as e:
            self._performance_metrics['errors_count'] += 1
            self._performance_metrics['last_error_time'] = time.time()
            logger.critical(f"❌ Failed to initialize bot: {str(e)}", exc_info=True)

            # Cleanup on failure
            await self._cleanup_on_failure()
            raise

    def _start_health_monitoring(self):
        """Start health monitoring background task"""
        async def health_monitor():
            while self._running:
                try:
                    await asyncio.sleep(self._health_check_interval)

                    # Check client connection
                    if self.client and not self.client.is_connected():
                        logger.warning("Telegram client disconnected, attempting reconnect...")
                        try:
                            await self.client.connect()
                        except Exception as e:
                            logger.error(f"Failed to reconnect client: {e}")

                    # Log performance metrics
                    uptime = time.time() - self._performance_metrics['start_time']
                    logger.info(f"Health check - Uptime: {uptime:.0f}s, Messages: {self._performance_metrics['messages_processed']}, Errors: {self._performance_metrics['errors_count']}")

                except Exception as e:
                    logger.error(f"Health monitoring error: {e}")

        task = asyncio.create_task(health_monitor())
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _cleanup_on_failure(self):
        """Cleanup resources on initialization failure"""
        try:
            if self.client and self.client.is_connected():
                await self.client.disconnect()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    def _register_handlers(self):
        """Register all event handlers with error wrapping"""
        prefix = re.escape(self.config.bot_prefix)

        # Wrap handlers with error handling
        def wrap_handler(handler_func):
            async def wrapped_handler(event):
                try:
                    self._performance_metrics['messages_processed'] += 1
                    await handler_func(event)
                except Exception as e:
                    self._performance_metrics['errors_count'] += 1
                    self._performance_metrics['last_error_time'] = time.time()
                    logger.error(f"Handler error in {handler_func.__name__}: {e}", exc_info=True)

                    # Send error message to user if possible
                    try:
                        await event.reply("❌ Terjadi kesalahan internal. Silakan coba lagi nanti.")
                    except:
                        pass
            return wrapped_handler

        # Core commands
        self.client.add_event_handler(
            wrap_handler(handle_start),
            events.NewMessage(pattern=rf'^{prefix}start$')
        )
        self.client.add_event_handler(wrap_handler(handle_button_press), events.CallbackQuery())
        self.client.add_event_handler(
            wrap_handler(handle_help),
            events.NewMessage(pattern=rf'^{prefix}help$')
        )
        self.client.add_event_handler(
            wrap_handler(handle_stats),
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
