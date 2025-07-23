"""
Enhanced Pinfairy Bot with service-based architecture
Main bot file with improved error handling, monitoring, and configuration management
"""

import asyncio
import sys
import signal
from typing import Optional

from telethon import TelegramClient, events
from telethon.tl.custom import Button

# Import services and utilities
from services.config_manager import load_config, get_config
from services.database import init_db
from services.monitoring import start_monitoring, stop_monitoring
from utils.logger import get_logger
from exceptions import ConfigurationException

# Import handlers
from handlers.commands import (
    handle_start, handle_pinterest_photo, handle_pinterest_video,
    handle_help, handle_stats, handle_board_link, handle_alive,
    handle_search, handle_profile, handle_history, handle_quota,
    handle_config, handle_leaderboard, handle_feedback,
    handle_backup, handle_restore
)
from handlers.callbacks import handle_button_press

logger = get_logger(__name__)

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
            await init_db()
            logger.info("✅ Database initialized")
            
            # Start monitoring
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
        import re
        
        prefix = re.escape(self.config.bot_prefix)
        
        # Core commands
        self.client.add_event_handler(
            handle_start,
            events.NewMessage(pattern=rf'^{prefix}start$')
        )
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
        
        # Admin commands
        if self.config.admin_ids:
            self.client.add_event_handler(
                handle_backup,
                events.NewMessage(pattern=rf'^{prefix}backup$')
            )
            self.client.add_event_handler(
                handle_restore,
                events.NewMessage(pattern=rf'^{prefix}restore$')
            )
        
        # Callback handler
        self.client.add_event_handler(handle_button_press, events.CallbackQuery())
    
    def _setup_auto_detection(self):
        """Setup automatic Pinterest link detection"""
        if not self.config.features.get("auto_detect", True):
            return
        
        @self.client.on(events.NewMessage(incoming=True))
        async def auto_detect_link(event):
            """Auto-detect Pinterest links in messages"""
            if not event.text or event.text.startswith(self.config.bot_prefix):
                return
            
            from utils.validators import URLValidator
            
            # Extract Pinterest URLs
            urls = URLValidator.extract_pinterest_urls(event.text)
            if not urls:
                return
            
            url = urls[0]  # Take first URL
            
            # Validate URL
            from utils.validators import validate_pinterest_url
            validation = await validate_pinterest_url(url)
            
            if not validation["is_valid"]:
                if validation.get("is_dead"):
                    await event.reply(
                        f"⚠️ Link terdeteksi, tapi sepertinya sudah mati atau tidak valid.\n\n`{url}`",
                        buttons=[[Button.inline("🗑️ Tutup", data="close_help")]]
                    )
                return
            
            # Create action buttons based on URL type
            buttons = []
            url_type = validation.get("url_type", "unknown")
            
            if url_type == "pin":
                buttons.append([Button.inline("📷 Download Foto", data=f"auto_photo:{url}")])
                buttons.append([Button.inline("🎬 Download Video", data=f"auto_video:{url}")])
            elif url_type in ["board", "user"]:
                buttons.append([Button.inline("🗂️ Download Board", data=f"auto_board:{url}")])
            
            if not buttons:
                return
            
            buttons.append([Button.inline("🗑️ Tutup", data="close_help")])
            
            await event.reply(
                f"🔗 Link Pinterest terdeteksi!\n\nPilih aksi untuk:\n`{url}`",
                buttons=buttons
            )
    
    def _setup_background_tasks(self):
        """Setup background tasks"""
        async def cleanup_task():
            """Periodic cleanup task"""
            while self._running:
                try:
                    from core import clean_temp_files
                    await clean_temp_files()
                    
                    # Clean expired cache
                    from services.database import db_service
                    await db_service.clear_expired_cache()
                    
                    # Clean old data
                    await db_service.cleanup_old_data(30)  # 30 days
                    
                    await asyncio.sleep(3600)  # Run every hour
                    
                except Exception as e:
                    logger.error(f"Error in cleanup task: {str(e)}", exc_info=True)
                    await asyncio.sleep(300)  # Wait 5 minutes on error
        
        async def health_check_task():
            """Periodic health check task"""
            while self._running:
                try:
                    from services.monitoring import get_health_status
                    health = await get_health_status()
                    
                    if health["overall_status"] != "healthy":
                        logger.warning(f"Health check failed: {health['critical_failures']}")
                    
                    await asyncio.sleep(300)  # Run every 5 minutes
                    
                except Exception as e:
                    logger.error(f"Error in health check task: {str(e)}", exc_info=True)
                    await asyncio.sleep(60)  # Wait 1 minute on error
        
        # Start background tasks
        asyncio.create_task(cleanup_task())
        asyncio.create_task(health_check_task())
    
    async def run(self):
        """Run the bot"""
        try:
            self._running = True
            logger.info("🚀 Pinfairy Bot is now online!")
            
            # Wait for shutdown signal
            await self._shutdown_event.wait()
            
        except Exception as e:
            logger.critical(f"❌ Critical error in bot runtime: {str(e)}", exc_info=True)
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown"""
        if not self._running:
            return
        
        logger.info("🛑 Shutting down Pinfairy Bot...")
        self._running = False
        
        try:
            # Stop monitoring
            await stop_monitoring()
            logger.info("✅ Monitoring services stopped")
            
            # Close database connections
            from services.database import db_service
            await db_service.close()
            logger.info("✅ Database connections closed")
            
            # Disconnect Telegram client
            if self.client and self.client.is_connected():
                await self.client.disconnect()
                logger.info("✅ Telegram client disconnected")
            
            logger.info("🏁 Pinfairy Bot shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {str(e)}", exc_info=True)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating shutdown...")
        self._shutdown_event.set()

async def main():
    """Main entry point"""
    bot = PinfairyBot()
    
    # Setup signal handlers
    def signal_handler(signum, frame):
        bot.signal_handler(signum, frame)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Initialize bot
        await bot.initialize()
        
        # Run bot
        await bot.run()
        
    except ConfigurationException as e:
        logger.critical(f"❌ Configuration error: {str(e)}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("⌨️ Keyboard interrupt received")
    except Exception as e:
        logger.critical(f"❌ Unexpected error: {str(e)}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Goodbye!")
    except Exception as e:
        logger.critical(f"❌ Fatal error: {str(e)}", exc_info=True)
        sys.exit(1)