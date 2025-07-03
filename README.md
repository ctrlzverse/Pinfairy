
<p align="center">
  <img src="https://github.com/images/mona-whisper.gif" alt="Pinfairybot Logo" width="150"/>
</p>

<h1 align="center">
  <b>✨ Pinfairybot ✨</b>
</h1>

---

## 🌱 About

PinfairyBot is a lightweight Telegram bot that helps you download images directly from Pinterest just by sending a link. Fast, simple, and magical—like a little fairy delivering your favorite pins! ✨

---

## 🛠️ Features

- Download Pinterest images and videos by sending links.
- Supports inline buttons for interactive navigation.
- Handles commands like `/start`, `/help`, `/stats`, and `/alive`.
- Integrates with Pinterest to fetch images and videos using web scraping techniques.

---

## ⚙️ Setup

### Prerequisites

- Python 3.8 or higher
- Required libraries in `requirements.txt`

### Installation Steps

1. Clone the repository:

   ```bash
   git clone https://github.com/aeswnh/Pinfairybot.git
   cd Pinfairybot
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Set up your `.env` file with necessary environment variables (e.g., Telegram API keys, channel settings).

4. Run the bot:

   ```bash
   python bot.py
   ```

---

## 🔌 Plugin System

Pinfairybot is designed to be modular. The bot uses handler modules for different Telegram commands and callbacks. You can easily extend the bot by adding more modules to the `handlers` and `modules` directories.

---

## 📝 Credits

- Developed with ❤️ by [aes-co](https://github.com/aes-co/@aesneverhere)
- Uses [Telethon](https://github.com/LonamiWebs/Telethon) for Telegram integration.
- Web scraping powered by [Playwright](https://github.com/microsoft/playwright) and [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/).

---

## 📜 License

This project is licensed under the MIT License.

---

## 🤝 Contribute

We welcome contributions! Please refer to the [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to contribute.

---

## 🚀 Deploy to Replit

You can easily deploy this bot to Replit by clicking the button below:

<p align="center">
  <a href="https://replit.com/github/aeswnh/Pinfairybot" target="_blank">
    <img src="https://replit.com/badge/github/aeswnh/Pinfairybot" alt="Deploy to Replit" width="200"/>
  </a>
</p>

Made with ❤️ by aes-co/@aesneverhere
