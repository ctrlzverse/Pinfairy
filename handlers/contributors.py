import logging
from telethon.tl.custom import Button

logger = logging.getLogger(__name__)

async def handle_contributors(event):
    """Handle .contributors command to display project contributors."""
    try:
        contributors_text = """**🧚 Pinfairy Bot - Contributors** ✨

**👥 Core Team:**
• **aes** - Creator & Maintainer
  - Initial development, Pinterest integration, core features

**🤝 Contributors Welcome!**
Kami terbuka untuk kontribusi dari komunitas!

**💡 Cara Berkontribusi:**
1. Fork repository di GitHub
2. Buat fitur baru atau perbaiki bug
3. Kirim Pull Request
4. Jadilah bagian dari pengembangan!

**📋 Daftar Kontribusi:**
- Bug fixes
- Fitur baru
- Dokumentasi
- Optimasi kode

**📞 Kontak:**
- GitHub: @aes-co/PinfairyBot
- Telegram: @aesneverhere

**🎯 Untuk melihat daftar lengkap kontributor:**
Gunakan `.contributors full` atau kunjungi file CONTRIBUTORS.md

**Terima kasih telah menggunakan Pinfairy Bot!** 🧚✨"""

        await event.reply(
            contributors_text,
            buttons=[
                [Button.url("📂 Lihat Daftar Lengkap", "https://github.com/aes-co/PinfairyBot/blob/main/CONTRIBUTORS.md")],
                [Button.url("⭐ GitHub Repository", "https://github.com/aes-co/PinfairyBot")],
                [Button.inline("🗑️ Tutup", data="close_help")]
            ]
        )
        
    except Exception as e:
        logger.error(f"Error di handle_contributors: {e}", exc_info=True)
        await event.reply("❌ Terjadi kesalahan saat menampilkan kontributor.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
