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
- **Auto-Detect Links** - Automatically detects Pinterest links in chat and offers download options.
- **High-Quality Downloads** - Automatically selects highest resolution available.
- **Smart Deduplication** - Removes duplicate images from board downloads.
- **Multiple Formats** - Support for photos, videos, and entire boards.
- **Batch Processing** - Download entire Pinterest boards as ZIP or albums.
- **Search Integration** - Search and download Pinterest pins directly.

### 👤 User Management
- **User Profiles** - Track download statistics and activity.
- **Download History** - View last 10 download attempts with status.
- **Daily Quotas** - 100 downloads per day with automatic reset.
- **Activity Tracking** - Monitor user engagement and usage patterns.
- **Leaderboard** - View the top downloaders.

### ⚙️ Configuration System
- **Interactive Settings** - Easy-to-use configuration interface with buttons.
- **Multi-language Support** - Indonesian and English languages.
- **Quality Options** - Choose between High/Medium/Low quality.
- **Notification Controls** - Enable/disable bot notifications.

### 🔒 Security & Performance
- **Rate Limiting** - Prevents spam with 3-second cooldowns.
- **Input Validation** - Comprehensive URL and query validation.
- **Anti-Dead Link** - Checks if a link is valid before processing.
- **Performance Monitoring** - Real-time system metrics tracking.
- **Automatic Cleanup** - Scheduled file cleanup and maintenance.

### 👑 Admin Features
- **Backup & Restore** - Admins can backup and restore the bot's database.
- **Feedback System** - Users can send feedback and feature requests to the admin.

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
.leaderboard       - View the top downloaders
.feedback          - Send feedback or feature requests
```

### ℹ️ Information Commands
```
.start             - Welcome message and introduction
.help              - Complete command reference
.stats             - Global bot statistics
.alive             - Bot status and system info
```

### 👑 Admin Commands
```
.backup            - Backup the bot's database
.restore           - Restore the bot's database
```

---

## 🚀 Deployment

### 🖥️ Local / VPS (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/aes-co/Pinfairybot.git
    cd Pinfairybot
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up environment variables:**
    Create a `.env` file by copying `.env.example` and fill in your credentials.
    ```bash
    cp .env.example .env
    # Edit .env with your values
    ```

4.  **Install Playwright browsers:**
    ```bash
    playwright install
    ```

5.  **Run the bot:**
    ```bash
    python bot.py
    ```

### ☁️ Replit (Cloud Deployment)

Due to Replit's limitations, Playwright cannot run locally. The bot is configured to use a remote browser via [browserless.io](https://www.browserless.io/).

1.  **Fork the repository** on GitHub.

2.  **Create a new Replit** and import the forked repository.

3.  **Get a `browserless.io` API Token:**
    -   Sign up for a **free account** at [browserless.io](https://www.browserless.io/).
    -   Copy your API token.

4.  **Add Replit Secrets:**
    -   In your Replit project, go to the "Secrets" tab.
    -   Add your Telegram and `browserless.io` credentials:
        -   `API_ID`: Your Telegram API ID.
        -   `API_HASH`: Your Telegram API Hash.
        -   `BOT_TOKEN`: Your Telegram Bot Token.
    -   `ADMIN_IDS`: Your user ID for admin commands.
    -   `BROWSERLESS_TOKEN`: Your token from `browserless.io`.
    -   `BOT_PREFIX`: Custom command prefix (e.g., `.`, `!`, `/`). Default is `/`.

5.  **Run the bot:**
    -   Click the "Run" button. Replit will automatically install dependencies and start the bot. No need to run `playwright install`.

---

## 🙏 Acknowledgements

A special thanks to the following for their invaluable contributions:

-   **[OnlineProxy-io](https://github.com/OnlineProxy-io)**: For providing the crucial insight and solution to run Playwright on limited environments like Replit using a remote browser service. This project's Replit compatibility is a direct result of their [helpful suggestion](https://github.com/aes-co/Pinfairybot/issues/1#issuecomment-3031631107).

---

## 🏗️ Architecture

-   **Modular Design**: Separated handlers for commands and callbacks.
-   **Database Integration**: SQLite for user data and performance metrics.
-   **Async Processing**: Non-blocking operations for better performance.
-   **Remote Browser**: Uses `browserless.io` for Playwright tasks on limited platforms.

---

## 📞 Support

-   **Issues**: [GitHub Issues](https://github.com/aes-co/Pinfairybot/issues)
-   **Telegram**: [@aesneverhere](https://t.me/aesneverhere)

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/aes-co">aes-co</a>
</p>