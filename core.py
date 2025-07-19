import logging
import os
import glob
import time
import sqlite3
import zipfile
import shutil
import asyncio
import httpx
import re
import psutil
import platform
import math
import json
from datetime import datetime
from telethon import events
from telethon.tl.custom import Button
from telethon.utils import get_display_name
from modules.pinterest import get_pinterest_photo_data, get_pinterest_video_data, get_all_pins_with_pagination, search_pins

logger = logging.getLogger(__name__)
DB_FILE = "bot_stats.db"
FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "@aes_hub")
DOWNLOADS_DIR = "downloads"
URL_PATTERN = re.compile(r'https?://[^\s]+')
BOT_START_TIME = datetime.utcnow()

# Rate limiting storage
user_last_request = {}
RATE_LIMIT_SECONDS = 3  # Minimum 3 seconds between requests per user

def validate_pinterest_url(url: str) -> dict:
    """Validate if URL is a valid Pinterest URL."""
    if not url or not isinstance(url, str):
        return {"is_valid": False, "message": "URL tidak valid.", "is_dead": False}
    
    # Clean URL
    url = url.strip()
    
    # Check if it's a valid URL format
    if not re.match(r'^https?://', url):
        return {"is_valid": False, "message": "URL harus dimulai dengan http:// atau https://", "is_dead": False}
    
    # Check if it's Pinterest domain
    pinterest_domains = ['pinterest.com', 'pin.it', 'www.pinterest.com']
    if not any(domain in url for domain in pinterest_domains):
        return {"is_valid": False, "message": "URL harus dari domain Pinterest (pinterest.com atau pin.it)", "is_dead": False}
    
    # Check URL length (prevent extremely long URLs)
    if len(url) > 2000:
        return {"is_valid": False, "message": "URL terlalu panjang.", "is_dead": False}

    # Check if link is alive
    try:
        with httpx.Client() as client:
            r = client.head(url, follow_redirects=True, timeout=10.0)
            if r.status_code != 200:
                return {"is_valid": False, "message": "Link tidak valid atau sudah mati.", "is_dead": True}
    except Exception as e:
        logger.warning(f"Gagal memeriksa link {url}: {e}")
        return {"is_valid": False, "message": "Gagal memeriksa link.", "is_dead": True}
    
    return {"is_valid": True, "url": url, "is_dead": False}

def check_rate_limit(user_id: int) -> dict:
    """Check if user is rate limited."""
    current_time = time.time()
    
    if user_id in user_last_request:
        time_diff = current_time - user_last_request[user_id]
        if time_diff < RATE_LIMIT_SECONDS:
            remaining = RATE_LIMIT_SECONDS - time_diff
            return {
                "allowed": False, 
                "message": f"⏳ Tunggu {remaining:.1f} detik sebelum request berikutnya."
            }
    
    user_last_request[user_id] = current_time
    return {"allowed": True}

# Database constants
DEFAULT_DAILY_QUOTA = 100
DEFAULT_SETTINGS = {
    "language": "id",
    "notifications": True,
    "download_quality": "high"
}

def init_db():
    """Initialize database with all required tables."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        
        # Download stats table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS download_stats (
                media_type TEXT PRIMARY KEY,
                count INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("INSERT OR IGNORE INTO download_stats (media_type, count) VALUES ('photo', 0)")
        cur.execute("INSERT OR IGNORE INTO download_stats (media_type, count) VALUES ('video', 0)")
        cur.execute("INSERT OR IGNORE INTO download_stats (media_type, count) VALUES ('board', 0)")
        
        # Users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                daily_quota INTEGER DEFAULT 100,
                downloads_today INTEGER DEFAULT 0,
                total_downloads INTEGER DEFAULT 0,
                quota_reset_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                settings TEXT DEFAULT '{"language": "id", "notifications": true, "download_quality": "high"}'
            );
        """)
        
        # Download history table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS download_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                media_type TEXT,
                url TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN,
                error_message TEXT,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        
        # Performance metrics table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                cpu_usage REAL,
                memory_usage REAL,
                disk_usage REAL,
                response_time REAL,
                error_count INTEGER DEFAULT 0
            )
        """)
        
        con.commit()

def increment_stat(media_type: str, amount: int = 1):
    """Increment download statistics."""
    with sqlite3.connect(DB_FILE) as con:
        con.cursor().execute(
            "UPDATE download_stats SET count = count + ? WHERE media_type = ?",
            (amount, media_type)
        )
        con.commit()

def get_stats():
    """Get global download statistics."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        cur.execute("SELECT media_type, count FROM download_stats")
        return {row[0]: row[1] for row in cur.fetchall()}

def get_user_profile(user_id: int) -> dict:
    """Get user profile and statistics."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT username, first_seen, last_active, daily_quota, 
                   downloads_today, total_downloads, quota_reset_at, settings
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "username": row[0],
            "first_seen": row[1],
            "last_active": row[2],
            "daily_quota": row[3],
            "downloads_today": row[4],
            "total_downloads": row[5],
            "quota_reset_at": row[6],
            "settings": json.loads(row[7])
        }

def update_user_activity(user_id: int, username: str = None):
    """Update user's last active time and create if not exists."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO users (user_id, username, last_active)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                last_active = CURRENT_TIMESTAMP,
                username = COALESCE(?, username)
        """, (user_id, username, username))
        con.commit()

def log_download(user_id: int, media_type: str, url: str, success: bool, error_message: str = None):
    """Log download attempt to history."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO download_history 
            (user_id, media_type, url, success, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, media_type, url, success, error_message))
        if success:
            cur.execute("""
                UPDATE users SET 
                downloads_today = downloads_today + 1,
                total_downloads = total_downloads + 1
                WHERE user_id = ?
            """, (user_id,))
        con.commit()

def get_download_history(user_id: int, limit: int = 10) -> list:
    """Get user's download history."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT media_type, url, timestamp, success, error_message
            FROM download_history
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """, (user_id, limit))
        return [
            {
                "media_type": row[0],
                "url": row[1],
                "timestamp": row[2],
                "success": row[3],
                "error_message": row[4]
            }
            for row in cur.fetchall()
        ]

def log_performance_metric():
    """Log current system performance metrics."""
    try:
        cpu = psutil.cpu_percent(interval=1)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        with sqlite3.connect(DB_FILE) as con:
            con.execute("""
                INSERT INTO performance_metrics 
                (cpu_usage, memory_usage, disk_usage)
                VALUES (?, ?, ?)
            """, (cpu, mem.percent, disk.percent))
            con.commit()
    except Exception as e:
        logger.error(f"Failed to log performance metrics: {e}")

def check_user_quota(user_id: int) -> dict:
    """Check if user has remaining quota for today."""
    profile = get_user_profile(user_id)
    if not profile:
        return {"allowed": True, "remaining": DEFAULT_DAILY_QUOTA}
    
    # Check if quota needs reset (daily reset)
    quota_reset = datetime.fromisoformat(profile["quota_reset_at"])
    now = datetime.utcnow()
    
    if now.date() > quota_reset.date():
        # Reset daily quota
        with sqlite3.connect(DB_FILE) as con:
            con.execute("""
                UPDATE users SET 
                downloads_today = 0,
                quota_reset_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            """, (user_id,))
            con.commit()
        profile["downloads_today"] = 0
    
    remaining = profile["daily_quota"] - profile["downloads_today"]
    return {
        "allowed": remaining > 0,
        "remaining": remaining,
        "quota": profile["daily_quota"]
    }

def get_user_settings(user_id: int) -> dict:
    """Get user's configuration settings."""
    profile = get_user_profile(user_id)
    if not profile:
        return DEFAULT_SETTINGS
    return profile["settings"]

def update_user_settings(user_id: int, settings: dict):
    """Update user's configuration settings."""
    current_settings = get_user_settings(user_id)
    current_settings.update(settings)
    
    with sqlite3.connect(DB_FILE) as con:
        con.execute("""
            UPDATE users SET settings = ?
            WHERE user_id = ?
        """, (json.dumps(current_settings), user_id))
        con.commit()

def get_performance_stats(hours: int = 24) -> dict:
    """Get performance statistics for the last N hours."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT AVG(cpu_usage), AVG(memory_usage), AVG(disk_usage),
                   MAX(cpu_usage), MAX(memory_usage), MAX(disk_usage),
                   COUNT(*) as samples
            FROM performance_metrics
            WHERE timestamp > datetime('now', '-{} hours')
        """.format(hours))
        row = cur.fetchone()
        if not row or row[6] == 0:
            return {"error": "No performance data available"}
        
        return {
            "avg_cpu": round(row[0], 2),
            "avg_memory": round(row[1], 2),
            "avg_disk": round(row[2], 2),
            "max_cpu": round(row[3], 2),
            "max_memory": round(row[4], 2),
            "max_disk": round(row[5], 2),
            "samples": row[6]
        }

async def process_profile_command(event):
    from telethon.tl.custom import Button
    user_id = event.sender_id
    username = event.sender.username or event.sender.first_name
    
    # Update user activity
    update_user_activity(user_id, username)
    
    profile = get_user_profile(user_id)
    if not profile:
        return await event.reply("❌ Profil tidak ditemukan.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
    
    quota_info = check_user_quota(user_id)
    
    profile_text = f"""
👤 **Profil Pengguna**

🆔 **User ID:** `{user_id}`
👤 **Username:** @{profile['username'] or 'N/A'}
📅 **Bergabung:** `{profile['first_seen'][:10]}`
🕐 **Terakhir Aktif:** `{profile['last_active'][:16]}`

📊 **Statistik Download:**
📈 **Total:** `{profile['total_downloads']}` file
📅 **Hari Ini:** `{profile['downloads_today']}`/`{profile['daily_quota']}`
⏳ **Sisa Quota:** `{quota_info['remaining']}`

⚙��� **Pengaturan:**
🌐 **Bahasa:** `{profile['settings']['language'].upper()}`
🔔 **Notifikasi:** `{'✅' if profile['settings']['notifications'] else '❌'}`
🎨 **Kualitas:** `{profile['settings']['download_quality'].title()}`
"""
    
    await event.reply(profile_text, buttons=[Button.inline("🔄 Refresh", data="refresh_profile"), Button.inline("🗑️ Tutup", data="close_help")])

async def process_history_command(event):
    from telethon.tl.custom import Button
    user_id = event.sender_id
    history = get_download_history(user_id, 10)
    
    if not history:
        return await event.reply("📝 **Riwayat Download**\n\nBelum ada riwayat download.", buttons=[Button.inline("🗑️ Tutup", data="close_help")])
    
    history_text = "📝 **Riwayat Download (10 Terakhir)**\n\n"
    
    for i, item in enumerate(history, 1):
        status = "✅" if item["success"] else "❌"
        media_type = item["media_type"].title()
        timestamp = item["timestamp"][:16]
        
        history_text += f"{i}. {status} **{media_type}** - `{timestamp}`\n"
        if not item["success"] and item["error_message"]:
            history_text += f"   ⚠️ {item['error_message'][:50]}...\n"
        history_text += "\n"
    
    await event.reply(history_text, buttons=[Button.inline("🔄 Refresh", data="refresh_history"), Button.inline("🗑️ Tutup", data="close_help")])

async def process_quota_command(event):
    from telethon.tl.custom import Button
    user_id = event.sender_id
    quota_info = check_user_quota(user_id)
    
    quota_text = f"""
📊 **Status Quota Harian**

⏳ **Sisa Quota:** `{quota_info['remaining']}`/`{quota_info['quota']}`
📈 **Persentase:** `{((quota_info['quota'] - quota_info['remaining']) / quota_info['quota'] * 100):.1f}%`

{'🟢 **Status:** Quota tersedia' if quota_info['allowed'] else '🔴 **Status:** Quota habis'}

💡 **Info:** Quota akan reset setiap hari pada 00:00 UTC
"""
    
    await event.reply(quota_text, buttons=[Button.inline("🔄 Refresh", data="refresh_quota"), Button.inline("🗑️ Tutup", data="close_help")])

async def process_config_command(event):
    """Process configuration command."""
    user_id = event.sender_id
    settings = get_user_settings(user_id)
    
    from telethon.tl.custom import Button
    
    config_text = f"""
⚙️ **Konfigurasi Bot**

🌐 **Bahasa:** `{settings['language'].upper()}`
🔔 **Notifikasi:** `{'Aktif' if settings['notifications'] else 'Nonaktif'}`
🎨 **Kualitas Download:** `{settings['download_quality'].title()}`

Pilih pengaturan yang ingin diubah:
"""
    
    buttons = [
        [
            Button.inline("🌐 Bahasa", data="config_language"),
            Button.inline("🔔 Notifikasi", data="config_notifications")
        ],
        [
            Button.inline("🎨 Kualitas", data="config_quality"),
            Button.inline("🔄 Reset", data="config_reset")
        ],
        [Button.inline("❌ Tutup", data="config_close")]
    ]
    
    await event.reply(config_text, buttons=buttons)

def humanbytes(size):
    if not size: return ""
    power = 1024
    n = 0
    power_labels = {0: '', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    while size >= power:
        size /= power
        n += 1
    return f"{size:.2f}{power_labels[n]}"

def get_speed_str(bytes_amount, elapsed):
    """Calculate and format download/upload speed."""
    if elapsed == 0:
        return '0 B/s'
    speed = bytes_amount / elapsed
    return humanbytes(speed) + '/s'

def get_system_info():
    """Get system information including CPU, RAM, and disk usage."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    uptime = format_uptime(BOT_START_TIME)
    return (f"--- ℹ️ System Info ---\n"
            f"Uptime: {uptime}\n"
            f"CPU: {cpu_percent}%\n"
            f"RAM: {ram.percent}% ({humanbytes(ram.used)}/{humanbytes(ram.total)})\n"
            f"Disk: {disk.percent}% ({humanbytes(disk.used)}/{humanbytes(disk.total)})")

def format_uptime(start_time):
    uptime = datetime.utcnow() - start_time; days = uptime.days
    hours, rem = divmod(uptime.seconds, 3600); minutes, seconds = divmod(rem, 60); parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    if seconds > 0: parts.append(f"{seconds}s")
    return " ".join(parts) if parts else "0s"

def _run_zip_process(board_name, image_urls, progress_callback=None):
    """Create ZIP file from image URLs."""
    try:
        # Ensure downloads directory exists
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
        
        # Create temporary directory for downloads
        temp_dir = os.path.join(DOWNLOADS_DIR, f"temp_{board_name}_{int(time.time())}")
        os.makedirs(temp_dir, exist_ok=True)
        
        total = len(image_urls)
        downloaded_count = 0
        
        with httpx.Client() as client:
            for i, url in enumerate(image_urls):
                try:
                    r = client.get(url, timeout=20.0)
                    if r.status_code == 200:
                        # Ensure we have a valid filename
                        filename = f"{i+1:04d}.jpg"
                        file_path = os.path.join(temp_dir, filename)
                        
                        with open(file_path, 'wb') as f:
                            f.write(r.content)
                        downloaded_count += 1
                        
                        logger.info(f"Downloaded image {i+1}/{total}: {filename}")
                    
                    if progress_callback:
                        progress_callback(i+1, total, 'download')
                        
                except Exception as e:
                    logger.warning(f"Gagal mengunduh {url}: {e}")
                    continue
        
        if downloaded_count == 0:
            shutil.rmtree(temp_dir)
            raise Exception("Tidak ada gambar yang berhasil diunduh")
        
        # Create ZIP file
        zip_filename = f"{board_name}_{int(time.time())}.zip"
        zip_path = os.path.join(DOWNLOADS_DIR, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    zf.write(file_path, arcname=filename)
        
        # Clean up temporary directory
        shutil.rmtree(temp_dir)
        
        logger.info(f"ZIP file created successfully: {zip_path}")
        return zip_path
        
    except Exception as e:
        logger.error(f"Error creating ZIP: {e}")
        # Clean up on error
        if 'temp_dir' in locals() and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        raise e
async def _download_for_album(board_name, image_urls, progress_callback=None):
    temp_dir = os.path.join(DOWNLOADS_DIR, board_name); os.makedirs(temp_dir, exist_ok=True)
    downloaded_paths = []
    async with httpx.AsyncClient() as client:
        for i, url in enumerate(image_urls):
            path = os.path.join(temp_dir, f"{i+1:04d}.jpg")
            try:
                r = await client.get(url, timeout=20.0)
                if r.status_code == 200:
                    with open(path, 'wb') as f: f.write(r.content)
                    downloaded_paths.append(path)
                if progress_callback:
                    await progress_callback(i+1, len(image_urls), 'download')
            except Exception as e:
                logger.warning(f"Gagal mengunduh {url} untuk album: {e}")
    return temp_dir, downloaded_paths
async def _progress_message(event, current, total, stage, msg=None):
    percent = int((current/total)*100) if total else 0
    bar = '█' * (percent // 10) + '░' * (10 - percent // 10)
    text = f"{'⬇️' if stage=='download' else '⬆️'} {stage.capitalize()} {current}/{total} [{bar}] {percent}%"
    if msg:
        await msg.edit(text)
    return text
async def _fetch_and_save(client, url, path):
    try:
        r = await client.get(url, timeout=20.0)
        if r.status_code == 200:
            with open(path, 'wb') as f: f.write(r.content)
            return path
    except Exception as e: logger.warning(f"Gagal mengunduh {url} untuk album: {e}")
    return None

async def process_alive_command(event):
    uptime = format_uptime(BOT_START_TIME); cpu_percent = psutil.cpu_percent(interval=1)
    ram = psutil.virtual_memory(); ram_total = humanbytes(ram.total); ram_used = humanbytes(ram.used); ram_percent = ram.percent
    disk = psutil.disk_usage('/'); disk_total = humanbytes(disk.total); disk_used = humanbytes(disk.used); disk_percent = disk.percent
    alive_text = (f"**PinfairyBot is alive!** 🧚\n\n"
                  f"⏳ **Uptime:** `{uptime}`\n"
                  f"🐍 **Python:** `{platform.python_version()}`\n\n"
                  f"🖥️ **CPU:** `[{'█' * int(cpu_percent / 10):<10}] {cpu_percent}%`\n"
                  f"💾 **RAM:** `[{'█' * int(ram_percent / 10):<10}] {ram_percent}%` (`{ram_used}/{ram_total}`)\n"
                  f"💽 **Disk:** `[{'█' * int(disk_percent / 10):<10}] {disk_percent}%` (`{disk_used}/{disk_total}`)")
    await event.reply(alive_text)

async def process_search_command(event, query: str):
    msg = await event.reply(f"🔎 Mencari pin untuk **'{query}'**...")
    try:
        search_result = await search_pins(query, limit=10)
        if not search_result.get("is_success"): return await msg.edit(f"⚠️ {search_result.get('message')}")
        pins = search_result.get("pins", [])
        await msg.edit(f"✅ Ditemukan {len(pins)} hasil! Mengunduh gambar untuk album...")
        search_name = re.sub(r'\W+', '_', query)
        temp_dir, downloaded_paths = await _download_for_album(search_name, [p['url'] for p in pins])
        if not downloaded_paths: return await msg.edit("Gagal mengunduh gambar untuk hasil pencarian.")
        await event.client.send_file(event.chat_id, file=downloaded_paths, caption=f"Berikut hasil pencarian teratas untuk **'{query}'**", reply_to=event.message)
        await msg.delete(); shutil.rmtree(temp_dir)
    except Exception as e: logger.error(f"Error di process_search_command: {e}", exc_info=True); await msg.edit(f"❌ Terjadi kesalahan fatal.")

async def process_pinterest_board(event, url: str, mode: str):
    try:
        board_data = await get_all_pins_with_pagination(url)
        if not board_data.get("is_success"): 
            return await event.edit(f"⚠️ {board_data.get('message')}")
        image_urls = board_data.get("image_urls")
        board_name = url.strip("/").split("/")[-1]
        total_images = len(image_urls)
        msg = await event.edit(f"✅ Ditemukan **{total_images}** pin unik.\nMulai mengunduh untuk mode **{mode.upper()}**...")
        original_message = await event.get_message()
        reply_to_id = original_message.reply_to.reply_to_msg_id if original_message.reply_to else None
        # Progress callback for download
        async def async_progress(current, total, stage):
            await _progress_message(event, current, total, stage, msg)
        def sync_progress(current, total, stage):
            asyncio.run_coroutine_threadsafe(_progress_message(event, current, total, stage, msg), asyncio.get_event_loop())
        if mode == 'zip':
            try:
                loop = asyncio.get_event_loop()
                zip_file_path = await loop.run_in_executor(None, _run_zip_process, board_name, image_urls, sync_progress)
                
                if zip_file_path and os.path.exists(zip_file_path):
                    # Upload progress
                    async def upload_progress(current, total):
                        await _progress_message(event, current, total, 'upload', msg)
                    
                    await event.client.send_file(
                        event.chat_id, 
                        file=zip_file_path, 
                        caption=f"✅ Arsip `.zip` dari board **'{board_name}'** ({total_images} gambar).",
                        reply_to=reply_to_id or event.message.id,
                        progress_callback=upload_progress
                    )
                    os.remove(zip_file_path)
                    logger.info(f"ZIP file sent and removed: {zip_file_path}")
                else:
                    await event.reply("❌ Gagal membuat file ZIP.")
                    
            except Exception as e:
                logger.error(f"Error in ZIP mode: {e}")
                await event.reply(f"❌ Gagal membuat ZIP: {str(e)}")
        elif mode == 'album':
            temp_dir, downloaded_paths = await _download_for_album(board_name, image_urls, async_progress)
            if not downloaded_paths: return await event.edit("Gagal mengunduh gambar.")
            for i in range(0, len(downloaded_paths), 10):
                batch = downloaded_paths[i:i+10]; caption = f"✅ Album dari board **'{board_name}'** ({i+1}-{i+len(batch)}/{total_images})" if i == 0 else ""
                # Upload progress per batch
                async def upload_progress(current, total):
                    await _progress_message(event, current, total, 'upload', msg)
                await event.client.send_file(event.chat_id, file=batch, caption=caption, reply_to=reply_to_id, progress_callback=upload_progress)
                await asyncio.sleep(1)
            shutil.rmtree(temp_dir)
        increment_stat("board"); increment_stat("photo", total_images); await msg.edit("✅ Selesai!")
    except Exception as e: logger.error(f"Error di process_pinterest_board: {e}", exc_info=True); await event.edit(f"❌ Terjadi kesalahan fatal.")
async def process_start_command(event):
    from telethon.tl.custom import Button
    user_name = get_display_name(event.sender)
    
    start_text = f"""
👋 **Halo, {user_name}! Selamat datang di Pinfairy Bot!** 🧚

Saya adalah asisten pribadimu untuk mengunduh semua media dari **Pinterest** dengan cepat dan mudah.

**✨ Fitur Andalan:**
- **Auto-Detect:** Cukup kirim link Pinterest di chat, saya akan langsung merespon!
- **Kualitas Tinggi:** Selalu memberikan gambar dan video dengan resolusi terbaik.
- **Download Board:** Unduh seluruh pin dari board favoritmu dalam sekejap.

Silakan jelajahi fitur lainnya melalui tombol di bawah ini!
"""
    
    buttons = [
        [
            Button.inline("🚀 Panduan Cepat", data="quick_guide"),
            Button.inline("📋 Daftar Perintah", data="full_help")
        ],
        [
            Button.url("📣 Channel Update", f"https://t.me/{FORCE_SUB_CHANNEL.lstrip('@')}"),
            Button.url("💻 Source Code", "https://github.com/aes-co/PinfairyBot")
        ]
    ]
    
    await event.respond(start_text, buttons=buttons)
async def process_help_command(event):
    from telethon.tl.custom import Button
    help_text = """**🧚 Bantuan Perintah Pinfairy Bot**

**📥 Download Commands:**
`.p <link>` - Download foto Pinterest
`.pv <link>` - Download video Pinterest  
`.pboard <link>` - Download semua foto dari board
`.search <query>` - Cari dan download pin

**👤 User Commands:**
`.profile` - Lihat profil dan statistik
`.history` - Riwayat download
`.quota` - Cek sisa quota harian
`.config` - Pengaturan bot
`.leaderboard` - Lihat papan peringkat downloader
`.feedback` - Kirim feedback atau request fitur

**ℹ️ Info Commands:**
`.alive` - Status bot dan sistem
`.stats` - Statistik global bot
`.help` - Bantuan ini


**💡 Tips:**
• **Auto-Detect:** Cukup kirim link Pinterest di chat, bot akan otomatis merespon!
• **Quota Harian:** 100 download/hari
• Konfigurasi bahasa, notifikasi, dan kualitas di `.config`"""
    
    await event.respond(help_text, buttons=[Button.inline("🗑️ Tutup", data="close_help")])
async def process_stats_command(event):
    from telethon.tl.custom import Button
    stats = get_stats()
    text = f"📊 **Statistik Bot**\n\n🖼️ Foto: **{stats.get('photo', 0)}**\n🎬 Video: **{stats.get('video', 0)}**\n🗂️ Board: **{stats.get('board', 0)}**"
    await event.respond(text, buttons=[Button.inline("🔄 Refresh", data="refresh_stats"), Button.inline("🗑️ Tutup", data="close_help")])

async def _send_media_with_buttons(event, data, media_type):
    from telethon.tl.custom import Button
    from telethon import events

    reply_to_msg = None
    if isinstance(event, events.CallbackQuery.Event):
        try:
            button_msg = await event.get_message()
            reply_to_msg = await button_msg.get_reply_message()
        except Exception:
            reply_to_msg = None
    else:
        reply_to_msg = event.message

    sent_message = await event.client.send_file(
        event.chat_id,
        file=data.get("media_url"),
        caption=f"✅ {media_type.capitalize()} berhasil diunduh!",
        reply_to=reply_to_msg
    )
    increment_stat(media_type)
    message_id = sent_message.id
    await sent_message.edit(
        buttons=[
            [Button.url("🔗 Lihat Post Asli", data.get("post_url"))],
            [Button.inline("ℹ️ Info", data=f"info_msg:{message_id}"), Button.inline("🔄 Download Lagi", data=f"redownload:{message_id}"), Button.inline("🗑️ Tutup", data=f"delete_confirmation:{message_id}")]
        ]
    )

async def process_pinterest_photo(event, url: str):
    msg = await event.reply("⏳ Mencari foto..."); data = await get_pinterest_photo_data(url)
    if not data.get("is_success"): return await msg.edit(f"⚠️ {data.get('message')}")
    await msg.delete(); await _send_media_with_buttons(event, data, "photo")

async def process_pinterest_video(event, url: str):
    msg = await event.reply("⏳ Mencari video..."); data = await get_pinterest_video_data(url)
    if not data.get("is_success"): return await msg.edit(f"⚠️ {data.get('message')}")
    await msg.delete(); await _send_media_with_buttons(event, data, "video")
async def process_pboard_callback(event):
    try:
        mode = event.data.decode().split('_')[1]
        button_message = await event.get_message()
        original_cmd_msg = await button_message.get_reply_message()
        if not original_cmd_msg or not original_cmd_msg.text:
            return await event.answer("Gagal membaca perintah asli.", alert=True)

        link_list = re.findall(r'https?://.*?(?=https?://|$)', original_cmd_msg.text)
        if not link_list:
            return await event.answer("Tidak ada link board valid ditemukan.", alert=True)

        msg = await event.edit(f"Found {len(link_list)} board link(s). Starting download in **{mode.upper()}** mode...")

        for i, url in enumerate(link_list, 1):
            board_data = await get_all_pins_with_pagination(url)
            if not board_data.get("is_success"):
                await event.reply(f"❌ Board {i}: {board_data.get('message')}")
                continue

            image_urls = board_data.get("image_urls")
            board_name = url.strip("/").split("/")[-1]
            total_images = len(image_urls)

            await msg.edit(f"Downloading board {i}/{len(link_list)}: **{board_name}** ({total_images} pins)")

            if mode == 'zip':
                try:
                    loop = asyncio.get_event_loop()
                    zip_file_path = await loop.run_in_executor(None, _run_zip_process, board_name, image_urls)
                    
                    if zip_file_path and os.path.exists(zip_file_path):
                        await event.client.send_file(
                            event.chat_id, 
                            file=zip_file_path, 
                            caption=f"✅ ZIP archive of board **'{board_name}'** ({total_images} images).",
                            reply_to=original_cmd_msg.id
                        )
                        os.remove(zip_file_path)
                        logger.info(f"ZIP file sent and removed in callback: {zip_file_path}")
                    else:
                        await event.reply(f"❌ Failed to create ZIP for board **{board_name}**")
                        
                except Exception as e:
                    logger.error(f"Error creating ZIP in callback: {e}")
                    await event.reply(f"❌ Error creating ZIP for board **{board_name}**: {str(e)}")
            else: # album mode
                temp_dir, downloaded_paths = await _download_for_album(board_name, image_urls)
                if not downloaded_paths:
                    await event.reply(f"Failed to download images for board **{board_name}**.")
                    continue
                
                for i in range(0, len(downloaded_paths), 10):
                    batch = downloaded_paths[i:i+10]
                    caption = f"✅ Album from board **'{board_name}'** ({i+1}-{i+len(batch)}/{total_images})" if i == 0 else ""
                    await event.client.send_file(event.chat_id, file=batch, caption=caption, reply_to=original_cmd_msg.id)
                    await asyncio.sleep(1)
                shutil.rmtree(temp_dir)

        await msg.edit("✅ All board downloads complete!")

    except Exception as e:
        logger.error(f"Error in process_pboard_callback: {e}", exc_info=True)
        await event.edit("❌ **Error!** An unexpected error occurred.")
async def process_main_callback(event):
    callback_data = event.data.decode("utf-8")
    if callback_data == "close_help":
        return await event.delete()
    if callback_data.startswith("sysinfo:"):
        # Show system info
        await event.answer(get_system_info(), alert=True)
        return
    try:
        action, target_id_str = callback_data.split(":", 1)
        target_id = int(target_id_str)
    except ValueError:
        action, target_id = callback_data, None
    if not target_id:
        return await event.answer()
    if action == "info_msg":
        try:
            msg = await event.client.get_messages(event.chat_id, ids=target_id)
            if not msg or not msg.media:
                return await event.answer("Media tidak ditemukan.", alert=True)
            file_size = 0; dimensions = "N/A"
            if msg.file:
                file_size = msg.file.size
            
            if msg.photo:
                # Find the largest photo size by dimensions, not by byte size
                photo_size_info = max(msg.photo.sizes, key=lambda s: s.w * s.h)
                dimensions = f"{photo_size_info.w} x {photo_size_info.h}"
            elif msg.document:
                for attr in msg.document.attributes:
                    if hasattr(attr, 'w') and hasattr(attr, 'h'):
                        dimensions = f"{attr.w} x {attr.h}"
                        break
            info_text = (f"--- ℹ️ Info Media ---\n"
                         f"Ukuran File: {humanbytes(file_size)}\n"
                         f"Dimensi: {dimensions}")
            return await event.answer(info_text, alert=True)
        except Exception as e:
            logger.error(f"Gagal menampilkan info: {e}")
            return await event.answer("Gagal mendapatkan info media.", alert=True)
    elif action == "delete_confirmation":
        await event.edit("Anda yakin?", buttons=[Button.inline("✅ Ya", data=f"delete_execute:{target_id}"), Button.inline("❌ Batal", data=f"delete_cancel:{target_id}")])
    elif action == "delete_execute":
        await event.client.delete_messages(event.chat_id, target_id)
        await event.delete()
    elif action == "delete_cancel":
        try:
            msg = await event.client.get_messages(event.chat_id, ids=target_id)
            original_buttons = [[Button.url("🔗 Lihat Post Asli", msg.buttons[0][0].url)], [Button.inline("ℹ️ Info", data=f"info_msg:{target_id}"), Button.inline("🗑️ Hapus", data=f"delete_confirmation:{target_id}")]]
            await event.edit(buttons=original_buttons)
        except Exception:
            await event.answer("Gagal membatalkan.")
async def process_auto_download(event):
    from telethon.tl.custom import Button
    button_data = event.data.decode("utf-8")
    action, url = button_data.split(":", 1)
    
    if action == "auto_photo":
        await process_pinterest_photo(event, url)
    elif action == "auto_board":
        await event.reply("Pilih mode pengiriman:", buttons=[
            Button.inline("Kirim sebagai ZIP 📦", data=f"pboard_zip:{url}"),
            Button.inline("Kirim sebagai Album 🖼️", data=f"pboard_album:{url}")
        ])
    elif action == "auto_video":
        await process_pinterest_video(event, url)

def get_leaderboard(limit: int = 10) -> list:
    """Get top downloaders from the database."""
    with sqlite3.connect(DB_FILE) as con:
        cur = con.cursor()
        cur.execute("""
            SELECT username, total_downloads
            FROM users
            WHERE total_downloads > 0
            ORDER BY total_downloads DESC
            LIMIT ?
        """, (limit,))
        return cur.fetchall()

async def process_leaderboard_command(event):
    from telethon.tl.custom import Button
    
    leaderboard_data = get_leaderboard(10)
    
    if not leaderboard_data:
        leaderboard_text = "🏆 **Papan Peringkat**\n\nBelum ada yang melakukan download. Jadilah yang pertama!"
    else:
        leaderboard_text = "🏆 **Top 10 Downloader**\n\n"
        for i, (username, total_downloads) in enumerate(leaderboard_data, 1):
            leaderboard_text += f"**{i}.** @{username or 'N/A'} - `{total_downloads}` downloads\n"
            
    await event.reply(
        leaderboard_text,
        buttons=[
            [Button.inline("Lihat Statistik Pribadi", data="my_stats"), Button.inline("🔄 Refresh", data="refresh_leaderboard")],
            [Button.inline("🗑️ Tutup", data="close_help")]
        ]
    )

async def process_feedback_command(event):
    from telethon.tl.custom import Button
    await event.reply(
        "Pilih jenis masukan:",
        buttons=[
            [Button.inline("Kirim Feedback", data="feedback_input")],
            [Button.inline("Kirim Request Fitur", data="feature_request_input")],
            [Button.inline("🗑️ Tutup", data="close_help")]
        ]
    )

async def process_leaderboard_callback(event):
    button_data = event.data.decode("utf-8")
    if button_data == "refresh_leaderboard":
        await process_leaderboard_command(event)
    elif button_data == "my_stats":
        await process_profile_command(event)

async def process_feedback_callback(event):
    from telethon.tl.custom import Button
    from telethon.tl.functions.messages import GetBotCallbackAnswerRequest

    button_data = event.data.decode("utf-8")
    feedback_type = "Feedback"
    if button_data == "feature_request_input":
        feedback_type = "Request Fitur"

    try:
        async with event.client.conversation(event.sender_id, timeout=300) as conv:
            await conv.send_message(f"✍️ Silakan tulis dan kirim **{feedback_type}** Anda. Saya akan meneruskannya ke admin.")
            
            response = await conv.get_response()
            
            # Forward to admin
            admin_id = int(os.getenv("ADMIN_IDS", "").split(',')[0]) # Ambil admin pertama
            await event.client.forward_messages(admin_id, response)
            
            await conv.send_message("✅ Terima kasih! Pesan Anda telah diteruskan ke admin.")
            await event.delete() # Hapus tombol asli

    except asyncio.TimeoutError:
        await event.reply("Waktu habis. Silakan coba lagi.")
    except Exception as e:
        logger.error(f"Gagal memproses feedback: {e}")
        await event.reply("Terjadi kesalahan saat memproses masukan Anda.")

def is_admin(user_id: int) -> bool:
    """Check if a user is an admin."""
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    if not admin_ids_str:
        return False
    admin_ids = [int(admin_id) for admin_id in admin_ids_str.split(',') if admin_id.strip().isdigit()]
    return user_id in admin_ids

async def process_backup_command(event):
    from telethon.tl.custom import Button
    if not is_admin(event.sender_id):
        return await event.reply(
            "🔒 Fitur ini hanya untuk admin. Hubungi pemilik bot jika ada pertanyaan.",
            buttons=[[Button.url("Hubungi Pemilik", "https://t.me/aesneverhere"), Button.inline("🗑️ Tutup", data="close_help")]]
        )
    await event.reply(
        "Konfirmasi backup database?",
        buttons=[
            [Button.inline("Backup Sekarang", data="do_backup")],
            [Button.inline("🗑️ Tutup", data="close_help")]
        ]
    )

async def process_restore_command(event):
    from telethon.tl.custom import Button
    if not is_admin(event.sender_id):
        return await event.reply(
            "🔒 Fitur ini hanya untuk admin. Hubungi pemilik bot jika ada pertanyaan.",
            buttons=[[Button.url("Hubungi Pemilik", "https://t.me/aesneverhere"), Button.inline("🗑️ Tutup", data="close_help")]]
        )
    await event.reply(
        "Konfirmasi restore database?",
        buttons=[
            [Button.inline("Restore Sekarang", data="do_restore")],
            [Button.inline("🗑️ Tutup", data="close_help")]
        ]
    )

async def process_admin_callback(event):
    from telethon.tl.custom import Button
    if not is_admin(event.sender_id):
        return await event.reply(
            "🔒 Fitur ini hanya untuk admin. Hubungi pemilik bot jika ada pertanyaan.",
            buttons=[[Button.url("Hubungi Pemilik", "https://t.me/aesneverhere"), Button.inline("🗑️ Tutup", data="close_help")]]
        )

    button_data = event.data.decode("utf-8")
    if button_data == "do_backup":
        try:
            backup_file = f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.db"
            shutil.copyfile(DB_FILE, backup_file)
            await event.client.send_file(
                event.chat_id,
                backup_file,
                caption=f"✅ **Backup Berhasil**\n\nFile: `{backup_file}`\nUkuran: `{humanbytes(os.path.getsize(backup_file))}`"
            )
            os.remove(backup_file)
            await event.answer("Backup berhasil dikirim!", alert=True)
        except Exception as e:
            logger.error(f"Backup gagal: {e}")
            await event.answer(f"❌ Backup gagal: {e}", alert=True)

    elif button_data == "do_restore":
        await event.answer("Silakan kirim file backup (.db) untuk merestore.", alert=True)
        # Here you would typically wait for the user to send a file
        # This requires conversation handling which is more complex.
        # For now, we just prompt the user.
        pass

async def process_start_callback(event):
    from telethon.tl.custom import Button
    button_data = event.data.decode("utf-8")
    
    if button_data == "quick_guide":
        guide_text = """**🚀 Panduan Cepat**

1. **Kirim Link:** Cukup kirim link Pinterest (foto, video, atau board) di chat ini.
2. **Pilih Aksi:** Tekan tombol yang muncul untuk mengunduh.
3. **Gunakan Perintah:** Untuk fitur lebih lanjut, gunakan perintah seperti `.profile`, `.history`, atau `.config`.

Selamat mencoba! ✨
"""
        await event.edit(guide_text, buttons=[[Button.inline("Kembali", data="back_to_start"), Button.inline("Tutup", data="close_help")]])
    
    elif button_data == "full_help":
        await process_help_command(event)
    
    elif button_data == "back_to_start":
        await process_start_command(event)

async def clean_temp_files(folder=DOWNLOADS_DIR, max_age_hours=1):
    """Clean temporary files older than specified hours."""
    if not os.path.isdir(folder):
        os.makedirs(folder, exist_ok=True)
        return
    
    now = time.time()
    max_age_seconds = max_age_hours * 3600
    
    for f in glob.glob(os.path.join(folder, '*')):
        try:
            if now - os.path.getmtime(f) > max_age_seconds:
                if os.path.isdir(f):
                    shutil.rmtree(f)
                else:
                    os.remove(f)
        except Exception as e:
            logger.error(f"Gagal menghapus item {f}: {e}")
