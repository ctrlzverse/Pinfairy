"""
Enhanced configuration management for Pinfairy Bot
Provides environment validation, schema validation, and configuration loading
"""

import os
import json
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path

from constants import (
    REQUIRED_ENV_VARS, OPTIONAL_ENV_VARS, DEFAULT_BOT_PREFIX,
    DEFAULT_DAILY_QUOTA, SUPPORTED_LANGUAGES, ADMIN_COMMANDS
)
from exceptions import ConfigurationException
from utils.logger import get_logger
from utils.validators import ConfigValidator

logger = get_logger(__name__)

@dataclass
class BotConfig:
    """Bot configuration data class"""
    # Telegram settings
    api_id: int
    api_hash: str
    bot_token: str
    bot_prefix: str = DEFAULT_BOT_PREFIX
    
    # Admin settings
    admin_ids: List[int] = field(default_factory=list)
    force_sub_channel: str = "@aes_hub"
    
    # Database settings
    database_url: str = "bot_stats.db"
    
    # External services
    browserless_token: Optional[str] = None
    redis_url: Optional[str] = None
    
    # Bot behavior
    daily_quota: int = DEFAULT_DAILY_QUOTA
    rate_limit_seconds: int = 3
    max_boards_per_request: int = 5
    
    # Logging
    log_level: str = "INFO"
    
    # Feature flags
    features: Dict[str, bool] = field(default_factory=dict)
    
    def __post_init__(self):
        """Validate configuration after initialization"""
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration values"""
        if not isinstance(self.api_id, int) or self.api_id <= 0:
            raise ConfigurationException("API_ID must be a positive integer")
        
        if not self.api_hash or len(self.api_hash) < 10:
            raise ConfigurationException("API_HASH must be a valid hash")
        
        if not self.bot_token or ':' not in self.bot_token:
            raise ConfigurationException("BOT_TOKEN must be a valid bot token")
        
        if self.daily_quota < 1:
            raise ConfigurationException("Daily quota must be at least 1")
        
        if self.rate_limit_seconds < 0:
            raise ConfigurationException("Rate limit seconds cannot be negative")

class ConfigManager:
    """Manages application configuration"""
    
    def __init__(self, config_file: str = None):
        self.config_file = config_file
        self.config: Optional[BotConfig] = None
        self._env_config: Dict[str, Any] = {}
        self._file_config: Dict[str, Any] = {}
    
    def load_config(self) -> BotConfig:
        """Load configuration from environment and files"""
        try:
            # Load environment variables
            self._load_environment_config()
            
            # Load file configuration if specified
            if self.config_file and os.path.exists(self.config_file):
                self._load_file_config()
            
            # Merge configurations (env takes precedence)
            merged_config = {**self._file_config, **self._env_config}
            
            # Create BotConfig instance
            self.config = self._create_bot_config(merged_config)
            
            logger.info("Configuration loaded successfully")
            return self.config
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}", exc_info=True)
            raise ConfigurationException(f"Configuration loading failed: {str(e)}")
    
    def _load_environment_config(self):
        """Load configuration from environment variables"""
        # Validate environment
        validation_result = ConfigValidator.validate_environment()
        
        if not validation_result["valid"]:
            missing_vars = validation_result["missing_vars"]
            invalid_vars = validation_result["invalid_vars"]
            
            error_msg = []
            if missing_vars:
                error_msg.append(f"Missing required environment variables: {', '.join(missing_vars)}")
            if invalid_vars:
                error_msg.append(f"Invalid environment variables: {', '.join(invalid_vars)}")
            
            raise ConfigurationException("; ".join(error_msg))
        
        self._env_config = validation_result["config"]
    
    def _load_file_config(self):
        """Load configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self._file_config = json.load(f)
            
            logger.info(f"Loaded configuration from {self.config_file}")
            
        except json.JSONDecodeError as e:
            raise ConfigurationException(f"Invalid JSON in config file: {str(e)}")
        except Exception as e:
            raise ConfigurationException(f"Failed to read config file: {str(e)}")
    
    def _create_bot_config(self, config_dict: Dict[str, Any]) -> BotConfig:
        """Create BotConfig instance from configuration dictionary"""
        try:
            # Extract required fields
            api_id = config_dict.get("API_ID")
            api_hash = config_dict.get("API_HASH")
            bot_token = config_dict.get("BOT_TOKEN")
            
            # Extract optional fields with defaults
            bot_prefix = config_dict.get("BOT_PREFIX", DEFAULT_BOT_PREFIX)
            admin_ids = config_dict.get("ADMIN_IDS", [])
            force_sub_channel = config_dict.get("FORCE_SUB_CHANNEL", "@aes_hub")
            database_url = config_dict.get("DATABASE_URL", "bot_stats.db")
            browserless_token = config_dict.get("BROWSERLESS_TOKEN")
            redis_url = config_dict.get("REDIS_URL")
            daily_quota = int(config_dict.get("DAILY_QUOTA", DEFAULT_DAILY_QUOTA))
            rate_limit_seconds = int(config_dict.get("RATE_LIMIT_SECONDS", 3))
            max_boards_per_request = int(config_dict.get("MAX_BOARDS_PER_REQUEST", 5))
            log_level = config_dict.get("LOG_LEVEL", "INFO")
            
            # Load feature flags
            features = self._load_feature_flags(config_dict)
            
            return BotConfig(
                api_id=api_id,
                api_hash=api_hash,
                bot_token=bot_token,
                bot_prefix=bot_prefix,
                admin_ids=admin_ids,
                force_sub_channel=force_sub_channel,
                database_url=database_url,
                browserless_token=browserless_token,
                redis_url=redis_url,
                daily_quota=daily_quota,
                rate_limit_seconds=rate_limit_seconds,
                max_boards_per_request=max_boards_per_request,
                log_level=log_level,
                features=features
            )
            
        except (ValueError, TypeError) as e:
            raise ConfigurationException(f"Invalid configuration values: {str(e)}")
    
    def _load_feature_flags(self, config_dict: Dict[str, Any]) -> Dict[str, bool]:
        """Load feature flags from configuration"""
        from constants import FEATURES
        
        features = FEATURES.copy()  # Start with defaults
        
        # Override with configuration values
        for feature, default_value in FEATURES.items():
            env_key = f"FEATURE_{feature.upper()}"
            if env_key in config_dict:
                try:
                    features[feature] = str(config_dict[env_key]).lower() in ('true', '1', 'yes', 'on')
                except:
                    logger.warning(f"Invalid value for feature flag {feature}, using default")
        
        return features
    
    def get_config(self) -> BotConfig:
        """Get current configuration"""
        if not self.config:
            self.load_config()
        return self.config
    
    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        if not self.config:
            return False
        return user_id in self.config.admin_ids
    
    def is_feature_enabled(self, feature: str) -> bool:
        """Check if feature is enabled"""
        if not self.config:
            return False
        return self.config.features.get(feature, False)
    
    def save_config_template(self, file_path: str = "config.json.example"):
        """Save configuration template file"""
        template = {
            "_comment": "Pinfairy Bot Configuration Template",
            "API_ID": "your_api_id_here",
            "API_HASH": "your_api_hash_here",
            "BOT_TOKEN": "your_bot_token_here",
            "BOT_PREFIX": "/",
            "ADMIN_IDS": "123456789,987654321",
            "FORCE_SUB_CHANNEL": "@your_channel",
            "BROWSERLESS_TOKEN": "optional_browserless_token",
            "DAILY_QUOTA": 100,
            "RATE_LIMIT_SECONDS": 3,
            "MAX_BOARDS_PER_REQUEST": 5,
            "LOG_LEVEL": "INFO",
            "features": {
                "auto_detect": True,
                "board_download": True,
                "video_download": True,
                "search_functionality": True,
                "user_profiles": True,
                "leaderboard": True,
                "feedback_system": True,
                "admin_panel": True,
                "performance_monitoring": True,
                "rate_limiting": True,
                "quota_system": True
            }
        }
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Configuration template saved to {file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save config template: {str(e)}")
            raise ConfigurationException(f"Failed to save config template: {str(e)}")
    
    def validate_startup_requirements(self) -> Dict[str, Any]:
        """Validate all startup requirements"""
        issues = []
        warnings = []
        
        try:
            config = self.get_config()
            
            # Check database accessibility
            if config.database_url and not config.database_url.startswith(('sqlite:', 'postgresql:', 'mysql:')):
                # Assume it's a file path for SQLite
                db_dir = os.path.dirname(config.database_url)
                if db_dir and not os.path.exists(db_dir):
                    try:
                        os.makedirs(db_dir, exist_ok=True)
                    except Exception as e:
                        issues.append(f"Cannot create database directory: {str(e)}")
            
            # Check admin configuration
            if not config.admin_ids:
                warnings.append("No admin users configured")
            
            # Check external services
            if not config.browserless_token:
                warnings.append("No Browserless token configured - browser features may not work on limited environments")
            
            # Check feature consistency
            if config.features.get("admin_panel") and not config.admin_ids:
                warnings.append("Admin panel enabled but no admin users configured")
            
            return {
                "valid": len(issues) == 0,
                "issues": issues,
                "warnings": warnings,
                "config": config
            }
            
        except Exception as e:
            return {
                "valid": False,
                "issues": [f"Configuration validation failed: {str(e)}"],
                "warnings": [],
                "config": None
            }

# Global configuration manager
config_manager = ConfigManager()

# Convenience functions
def load_config(config_file: str = None) -> BotConfig:
    """Load configuration"""
    if config_file:
        config_manager.config_file = config_file
    return config_manager.load_config()

def get_config() -> BotConfig:
    """Get current configuration"""
    return config_manager.get_config()

def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return config_manager.is_admin(user_id)

def is_feature_enabled(feature: str) -> bool:
    """Check if feature is enabled"""
    return config_manager.is_feature_enabled(feature)