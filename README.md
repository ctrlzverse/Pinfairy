<p align="center">
  <img src="https://github.com/images/mona-whisper.gif" alt="Pinfairy Logo" width="150"/>
</p>

<h1 align="center">
  <b>✨ Pinfairy ✨</b>
</h1>

<p align="center">
  Your magical assistant for downloading high-quality media from Pinterest, right within Telegram.
</p>

<p align="center">
    <a href="https://www.python.org/"><img src="https://img.shields.io/badge/Made%20with-Python-blue.svg" alt="Made with Python"></a>
    <a href="https://github.com/ctrlzverse/Pinfairy/stargazers"><img src="https://img.shields.io/github/stars/ctrlzverse/Pinfairy?style=social" alt="Stars"></a>
    <a href="https://github.com/ctrlzverse/Pinfairy/issues"><img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"></a>
</p>

---

## 🌱 About Pinfairy

**Pinfairy** is an advanced Telegram bot designed to be your all-in-one solution for downloading images and videos from Pinterest. Packed with intelligent features like duplicate detection, user management, and performance monitoring, Pinfairy is fast, smart, and magical—like a little fairy delivering your favorite pins! ✨

---

## 🚀 Key Features

### 📥 Powerful Download Capabilities
- **Auto-Detect Links**: Intelligently detects Pinterest links in chat and offers download options.
- **High-Quality Downloads**: Fetches the highest resolution available by default.
- **Smart Deduplication**: Automatically removes duplicate images when downloading from a board.
- **Multiple Formats Support**: Seamlessly download photos, videos, and entire boards.
- **Batch Processing**: Download entire Pinterest boards as a ZIP file or a media album.
- **Search Integration**: Search and download Pinterest pins directly from Telegram.

### 👤 Robust User Management
- **User Profiles**: Track your personal download statistics and activity.
- **Download History**: View your last 10 download attempts with their status.
- **Daily Quotas**: A fair usage quota of 100 downloads per day, with an automatic daily reset.
- **Leaderboard**: See who the top downloaders are.

### ⚙️ Intuitive Configuration
- **Interactive Settings**: A user-friendly, button-based interface for configuration.
- **Multi-language Support**: Switch between Indonesian and English.
- **Quality Options**: Choose your preferred download quality (High/Medium/Low).
- **Notification Controls**: Enable or disable bot notifications to your liking.

### 🔒 Security & Performance
- **Rate Limiting**: Prevents spam with a 3-second cooldown between commands.
- **Input Validation**: Ensures all URLs and queries are valid before processing.
- **Anti-Dead Link**: Checks link validity to prevent failed attempts.
- **Performance Monitoring**: Real-time tracking of system metrics.
- **Automatic Cleanup**: Scheduled file cleanup to keep the bot running smoothly.

### 👑 Admin Toolkit
- **Backup & Restore**: Admins can easily back up and restore the bot's database.
- **Feedback System**: A direct channel for users to send feedback and feature requests to the admin.

---

## 📋 Commands

Interact with the bot using these simple commands:

### 📥 Download Commands
```
.p <link>        - Download a Pinterest photo
.pv <link>       - Download a Pinterest video
.pboard <link>   - Download an entire Pinterest board
.search <query>  - Search for and download pins
```

### 👤 User Commands
```
.profile       - View your profile and statistics
.history       - View your download history
.quota         - Check your daily quota status
.config        - Access the bot's configuration settings
.leaderboard   - View the top downloaders
.feedback      - Send feedback or a feature request
```

### ℹ️ Information Commands
```
.start         - Display the welcome message
.help          - Get a complete command reference
.stats         - View global bot statistics
.alive         - Check bot status and system info
```

### 👑 Admin Commands
```
.backup        - Back up the bot's database
.restore       - Restore the bot's database
```

---

## 🚀 Deployment Guide

### 🖥️ Local / VPS (Recommended)

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/ctrlzverse/Pinfairy.git
    cd Pinfairy
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up environment variables:**
    Create a `.env` file by copying `.env.example` and fill in your credentials.
    ```bash
    cp .env.example .env
    # Edit the .env file with your values
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

Due to Replit's limitations, Playwright cannot run locally. This bot is configured to use a remote browser via **[browserless.io](https://www.browserless.io/)**.

1.  **Fork the repository** on GitHub.

2.  **Create a new Replit** and import your forked repository.

3.  **Get a `browserless.io` API Token:**
    - Sign up for a **free account** at [browserless.io](https://www.browserless.io/).
    - Copy your API token.

4.  **Add Replit Secrets:**
    - In your Replit project, go to the "Secrets" tab (lock icon).
    - Add your Telegram and `browserless.io` credentials:
        - `API_ID`: Your Telegram API ID.
        - `API_HASH`: Your Telegram API Hash.
        - `BOT_TOKEN`: Your Telegram Bot Token.
        - `ADMIN_IDS`: Your user ID for admin access.
        - `BROWSERLESS_TOKEN`: Your token from `browserless.io`.
        - `BOT_PREFIX`: Custom command prefix (e.g., `.`, `!`, `/`). Defaults to `/`.

5.  **Run the Bot:**
    - Click the "Run" button. Replit will automatically install dependencies and start the bot. You do **not** need to run `playwright install`.

---

## 🙏 Acknowledgements

A special thanks to the following for their invaluable contributions:

-   **[OnlineProxy-io](https://github.com/OnlineProxy-io)**: For providing the crucial insight and solution to run Playwright on limited environments like Replit using a remote browser service. This project's Replit compatibility is a direct result of their [helpful suggestion](https://github.com/ctrlzverse/Pinfairy/issues/1#issuecomment-3031631107).

---

## 🏗️ Architecture

-   **Modular Design**: Clean separation of handlers for commands and callbacks.
-   **Database Integration**: SQLite for user data and performance metrics.
-   **Async Processing**: Non-blocking operations for a responsive, high-performance experience.
-   **Remote Browser**: Utilizes `browserless.io` for Playwright tasks on resource-limited platforms.

---

## 📞 Support & Contributing

-   **Issues**: Found a bug or have a feature request? Open an issue on [GitHub Issues](https://github.com/ctrlzverse/Pinfairy/issues).
-   **Contact**: Reach out on Telegram at [@aesneverhere](https://t.me/aesneverhere).
-   **Contributions**: Pull requests are always welcome!

<p align="center">
  Made with ❤️ by <a href="https://github.com/ctrlzverse">ctrlzverse</a>
</p>
