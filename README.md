
<p align="center">
  <img src="https://github.com/images/mona-whisper.gif" alt="Pinfairybot Logo" width="150"/>
</p>

<h1 align="center">
  <b>✨ Pinfairybot ✨</b>
</h1>

<p align="center">
  <em>Advanced Pinterest Media Downloader Bot for Telegram</em>
</p>

---

## 🌱 About

PinfairyBot is an advanced Telegram bot that helps you download high-quality images and videos from Pinterest with intelligent features like duplicate detection, user management, and performance monitoring. Fast, smart, and magical—like a little fairy delivering your favorite pins! ✨

---

## 🚀 Features

### 📥 Download Features
- **High-Quality Downloads** - Automatically selects highest resolution available
- **Smart Deduplication** - Removes duplicate images from board downloads
- **Multiple Formats** - Support for photos, videos, and entire boards
- **Batch Processing** - Download entire Pinterest boards as ZIP or albums
- **Search Integration** - Search and download Pinterest pins directly

### 👤 User Management
- **User Profiles** - Track download statistics and activity
- **Download History** - View last 10 download attempts with status
- **Daily Quotas** - 100 downloads per day with automatic reset
- **Activity Tracking** - Monitor user engagement and usage patterns

### ⚙️ Configuration System
- **Interactive Settings** - Easy-to-use configuration interface
- **Multi-language Support** - Indonesian and English languages
- **Quality Options** - Choose between High/Medium/Low quality
- **Notification Controls** - Enable/disable bot notifications

### 🔒 Security & Performance
- **Rate Limiting** - Prevents spam with 3-second cooldowns
- **Input Validation** - Comprehensive URL and query validation
- **Performance Monitoring** - Real-time system metrics tracking
- **Automatic Cleanup** - Scheduled file cleanup and maintenance

---

## 📋 Commands

### 📥 Download Commands
```
.p <link>          - Download Pinterest photo
.pv <link>         - Download Pinterest video
.pboard <link>     - Download entire Pinterest board
.search <query>    - Search and download pins
```

### 👤 User Commands
```
.profile           - View your profile and statistics
.history           - View download history
.quota             - Check daily quota status
.config            - Bot configuration settings
```

### ℹ️ Information Commands
```
.start             - Welcome message and introduction
.help              - Complete command reference
.stats             - Global bot statistics
.alive             - Bot status and system info
```

---

## ⚙️ Setup

### Prerequisites

- Python 3.10 or higher
- Telegram Bot Token
- Pinterest access (no API key required)

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/aeswnh/Pinfairybot.git
   cd Pinfairybot
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   
   Or using Poetry:
   ```bash
   poetry install
   ```

3. **Set up environment variables:**
   Create a `.env` file with:
   ```env
   API_ID=your_telegram_api_id
   API_HASH=your_telegram_api_hash
   BOT_TOKEN=your_bot_token
   FORCE_SUB_CHANNEL=@your_channel
   ```

4. **Initialize Playwright:**
   ```bash
   playwright install chromium
   ```

5. **Run the bot:**
   ```bash
   python bot.py
   ```

---

## 🏗️ Architecture

### Project Structure
```
Pinfairybot/
├── bot.py                 # Main bot entry point
├── core.py               # Core functionality and utilities
├── config.py             # Configuration settings
├── handlers/             # Command and callback handlers
│   ├── commands.py       # Command handlers
│   └── callbacks.py      # Button callback handlers
├── modules/              # Feature modules
│   └── pinterest.py      # Pinterest scraping logic
├── downloads/            # Temporary download directory
├── requirements.txt      # Python dependencies
├── pyproject.toml       # Poetry configuration
└── FEATURES.md          # Detailed feature documentation
```

### Key Components

- **Modular Design** - Separated handlers for commands and callbacks
- **Database Integration** - SQLite for user data and performance metrics
- **Async Processing** - Non-blocking operations for better performance
- **Background Tasks** - Automated cleanup and monitoring
- **Error Handling** - Comprehensive error logging and user feedback

---

## 📊 Database Schema

The bot uses SQLite with the following tables:

- **users** - User profiles and settings
- **download_history** - Download attempt logs
- **download_stats** - Global download statistics
- **performance_metrics** - System performance data

---

## 🔧 Configuration

### User Settings
- **Language**: Indonesian (ID) / English (EN)
- **Notifications**: Enable/Disable bot notifications
- **Download Quality**: High/Medium/Low resolution options

### System Settings
- **Daily Quota**: 100 downloads per user (configurable)
- **Rate Limiting**: 3 seconds between requests
- **Max Boards**: 5 boards per request
- **File Cleanup**: Automatic cleanup after 1 hour

---

## 🚀 Advanced Features

### Smart Download System
- **Resolution Priority** - Always attempts highest quality first
- **Fallback Mechanisms** - Multiple scraping methods for reliability
- **Progress Tracking** - Real-time progress for large downloads
- **Error Recovery** - Automatic retry on temporary failures

### Performance Monitoring
- **System Metrics** - CPU, RAM, and disk usage tracking
- **Response Times** - API response time monitoring
- **Error Rates** - Download success/failure statistics
- **User Analytics** - Usage patterns and activity tracking

### Security Features
- **Input Sanitization** - Prevents malicious input
- **URL Validation** - Ensures Pinterest domain compliance
- **Quota Enforcement** - Prevents abuse with daily limits
- **Rate Limiting** - Protects against spam and overload

---

## 📈 Performance

- **Async Operations** - Non-blocking download processing
- **Memory Efficient** - Optimized for low resource usage
- **Scalable Design** - Handles multiple concurrent users
- **Background Processing** - Automated maintenance tasks

---

## 🔌 Plugin System

Pinfairybot features a modular plugin architecture:

- **Handler Modules** - Easy command and callback management
- **Feature Modules** - Isolated functionality for different services
- **Configuration System** - Centralized settings management
- **Database Abstraction** - Clean data access layer

---

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Commit your changes** (`git commit -m 'Add amazing feature'`)
4. **Push to the branch** (`git push origin feature/amazing-feature`)
5. **Open a Pull Request**

### Development Guidelines
- Follow PEP 8 style guidelines
- Add docstrings to all functions
- Include error handling for all operations
- Test new features thoroughly

---

## 📝 Credits

- **Developer**: [aes-co](https://github.com/aes-co) / [@aesneverhere](https://t.me/aesneverhere)
- **Framework**: [Telethon](https://github.com/LonamiWebs/Telethon) for Telegram integration
- **Web Scraping**: [Playwright](https://github.com/microsoft/playwright) and [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
- **HTTP Client**: [httpx](https://github.com/encode/httpx) for async requests
- **System Monitoring**: [psutil](https://github.com/giampaolo/psutil) for performance metrics

---

## 📜 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

## 🚀 Deployment Options

### 🖥️ VPS/Dedicated Server (Recommended)
Deployment pada VPS atau dedicated server memberikan performa terbaik dan support penuh untuk Playwright:

1. **Persiapan Server:**
   ```bash
   # Update system
   sudo apt update && sudo apt upgrade -y
   
   # Install dependencies
   sudo apt install -y python3-pip python3-venv git wget curl unzip
   
   # Install Chrome dependencies
   sudo apt install -y ca-certificates fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 \
   libatk1.0-0 libc6 libcairo2 libcups2 libdbus-1-3 libexpat1 libfontconfig1 libgbm1 libgcc1 libglib2.0-0 \
   libgtk-3-0 libnspr4 libnss3 libpango-1.0-0 libpangocairo-1.0-0 libstdc++6 libx11-6 libx11-xcb1 libxcb1 \
   libxcomposite1 libxcursor1 libxdamage1 libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 \
   lsb-release xdg-utils
   ```

2. **Clone & Setup:**
   ```bash
   # Clone repository
   git clone https://github.com/aeswnh/Pinfairybot.git
   cd Pinfairybot
   
   # Create virtual environment
   python3 -m venv .venv
   source .venv/bin/activate
   
   # Install requirements
   pip install -r requirements.txt
   
   # Install Playwright with dependencies
   playwright install chromium
   playwright install-deps chromium
   ```

3. **Configuration:**
   ```bash
   # Setup environment variables
   cp .env.example .env
   nano .env  # Edit with your credentials
   ```

4. **Run with PM2:**
   ```bash
   # Install PM2
   curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -
   sudo apt install -y nodejs
   sudo npm install -g pm2
   
   # Create PM2 config
   echo '{
     "apps": [{
       "name": "pinfairybot",
       "script": "python3",
       "args": "bot.py",
       "interpreter": ".venv/bin/python3",
       "cwd": "/path/to/Pinfairybot",
       "env": {
         "PYTHONUNBUFFERED": "1"
       }
     }]
   }' > ecosystem.config.json
   
   # Start bot
   pm2 start ecosystem.config.json
   pm2 save
   ```

### ☁️ Railway.app (Alternative)
Railway.app menyediakan environment yang mendukung Playwright:

1. **Fork repository** ke GitHub Anda

2. **Deploy di Railway:**
   - Buka [Railway.app](https://railway.app)
   - Connect dengan GitHub
   - Select repository yang sudah di-fork
   - Add environment variables dari `.env.example`
   - Railway akan mendeteksi dan menginstall dependencies otomatis

3. **Konfigurasi Build:**
   ```toml
   # railway.toml
   [build]
   builder = "nixpacks"
   buildCommand = "pip install -r requirements.txt && playwright install chromium && playwright install-deps chromium"
   
   [deploy]
   startCommand = "python bot.py"
   healthcheckPath = "/"
   restartPolicyType = "on_failure"
   ```

### 🌐 Google Cloud Run (Alternative)
Google Cloud Run juga mendukung Playwright dengan konfigurasi Docker:

1. **Buat Dockerfile:**
   ```dockerfile
   FROM mcr.microsoft.com/playwright/python:latest
   
   WORKDIR /app
   COPY . .
   
   RUN pip install -r requirements.txt
   RUN playwright install chromium
   
   CMD ["python", "bot.py"]
   ```

2. **Deploy:**
   ```bash
   # Build & push
   gcloud builds submit --tag gcr.io/PROJECT_ID/pinfairybot
   
   # Deploy to Cloud Run
   gcloud run deploy pinfairybot \
     --image gcr.io/PROJECT_ID/pinfairybot \
     --platform managed \
     --allow-unauthenticated
   ```

### ⚠️ Note for Replit Users
Replit memiliki keterbatasan dalam menjalankan Playwright. Sebagai alternatif, gunakan salah satu opsi deployment di atas atau modifikasi kode untuk menggunakan `requests` dan `BeautifulSoup4` sebagai pengganti Playwright.

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/aeswnh/Pinfairybot/issues)
- **Telegram**: [@aesneverhere](https://t.me/aesneverhere)
- **Channel**: [@aes_hub](https://t.me/aes_hub)

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/aes-co">aes-co</a>
</p>
