import logging, os, glob, time, sqlite3, zipfile, shutil, asyncio, httpx, re, psutil, platform
from datetime import datetime
from telethon import events
from telethon.tl.custom import Button
from telethon.utils import get_display_name
from modules.pinterest import get_pinterest_photo_data, get_pinterest_video_data, get_all_pins_with_pagination, search_pins

logger = logging.getLogger(__name__)
DB_FILE = "bot_stats.db"; FORCE_SUB_CHANNEL = os.getenv("FORCE_SUB_CHANNEL", "@aes_hub"); DOWNLOADS_DIR = "downloads"
URL_PATTERN = re.compile(r'https?://[^\s]+'); BOT_START_TIME = datetime.utcnow()

def init_db():
    with sqlite3.connect(DB_FILE) as con: cur = con.cursor(); cur.execute("CREATE TABLE IF NOT EXISTS download_stats (media_type TEXT PRIMARY KEY, count INTEGER NOT NULL DEFAULT 0)"); cur.execute("INSERT OR IGNORE INTO download_stats (media_type, count) VALUES ('photo', 0)"); cur.execute("INSERT OR IGNORE INTO download_stats (media_type, count) VALUES ('video', 0)"); cur.execute("INSERT OR IGNORE INTO download_stats (media_type, count) VALUES ('board', 0)"); con.commit()
def increment_stat(media_type: str, amount: int = 1):
    with sqlite3.connect(DB_FILE) as con: con.cursor().execute("UPDATE download_stats SET count = count + ? WHERE media_type = ?", (amount, media_type)); con.commit()
def get_stats():
    with sqlite3.connect(DB_FILE) as con: cur = con.cursor(); cur.execute("SELECT media_type, count FROM download_stats"); return {row[0]: row[1] for row in cur.fetchall()}

def humanbytes(size):
    if not size: return ""
    power = 1024
    n = 0
    power_labels = {0: '', 1: ' KB', 2: ' MB', 3: ' GB', 4: ' TB'}
    while size >= power:
        size /= power
        n += 1
    return f"{size:.2f}{power_labels[n]}"

def format_uptime(start_time):
    uptime = datetime.utcnow() - start_time; days = uptime.days
    hours, rem = divmod(uptime.seconds, 3600); minutes, seconds = divmod(rem, 60); parts = []
    if days > 0: parts.append(f"{days}d")
    if hours > 0: parts.append(f"{hours}h")
    if minutes > 0: parts.append(f"{minutes}m")
    if seconds > 0: parts.append(f"{seconds}s")
    return " ".join(parts) if parts else "0s"

def _run_zip_process(board_name, image_urls):
    temp_dir = os.path.join(DOWNLOADS_DIR, board_name); os.makedirs(temp_dir, exist_ok=True)
    with httpx.Client() as client:
        for i, url in enumerate(image_urls):
            try:
                r = client.get(url, timeout=20.0);
                if r.status_code == 200:
                    with open(os.path.join(temp_dir, f"{i+1:04d}.jpg"), 'wb') as f: f.write(r.content)
            except Exception as e: logger.warning(f"Gagal mengunduh {url}: {e}")
    zip_path = os.path.join(DOWNLOADS_DIR, f"{board_name}.zip");
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in os.listdir(temp_dir): zf.write(os.path.join(temp_dir, f), arcname=f)
    shutil.rmtree(temp_dir); return zip_path
async def _download_for_album(board_name, image_urls):
    temp_dir = os.path.join(DOWNLOADS_DIR, board_name); os.makedirs(temp_dir, exist_ok=True)
    async with httpx.AsyncClient() as client:
        tasks = [_fetch_and_save(client, url, os.path.join(temp_dir, f"{i+1:04d}.jpg")) for i, url in enumerate(image_urls)]
        results = await asyncio.gather(*tasks); downloaded_paths = [path for path in results if path is not None]
    return temp_dir, downloaded_paths
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
        if not board_data.get("is_success"): return await event.edit(f"⚠️ {board_data.get('message')}")
        image_urls = board_data.get("image_urls"); board_name = url.strip("/").split("/")[-1]; total_images = len(image_urls)
        await event.edit(f"✅ Ditemukan **{total_images}** pin unik.\nMulai mengunduh untuk mode **{mode.upper()}**...")
        original_message = await event.get_message(); reply_to_id = original_message.reply_to.reply_to_msg_id
        if mode == 'zip':
            loop = asyncio.get_event_loop(); zip_file_path = await loop.run_in_executor(None, _run_zip_process, board_name, image_urls)
            await event.client.send_file(event.chat_id, file=zip_file_path, caption=f"✅ Arsip `.zip` dari board **'{board_name}'**.", reply_to=reply_to_id)
            os.remove(zip_file_path)
        elif mode == 'album':
            temp_dir, downloaded_paths = await _download_for_album(board_name, image_urls)
            if not downloaded_paths: return await event.edit("Gagal mengunduh gambar.")
            for i in range(0, len(downloaded_paths), 10):
                batch = downloaded_paths[i:i+10]; caption = f"✅ Album dari board **'{board_name}'** ({i+1}-{i+len(batch)}/{total_images})" if i == 0 else ""
                await event.client.send_file(event.chat_id, file=batch, caption=caption, reply_to=reply_to_id)
                await asyncio.sleep(1)
            shutil.rmtree(temp_dir)
        increment_stat("board"); increment_stat("photo", total_images); await event.delete()
    except Exception as e: logger.error(f"Error di process_pinterest_board: {e}", exc_info=True); await event.edit(f"❌ Terjadi kesalahan fatal.")
async def process_start_command(event):
    await event.respond(f"👋 **Selamat Datang, {get_display_name(event.sender)}!**\n\nSaya Pinfairy, bot pengunduh media Pinterest. Gunakan `.help` untuk melihat fitur.", buttons=[[Button.url("</> Source Code", "https://github.com/aes-co/PinfairyBot"), Button.url("👑 Owner", "https://t.me/aesneverhere")], [Button.url("📣 Channel Update", f"https://t.me/{FORCE_SUB_CHANNEL.lstrip('@')}")]])
async def process_help_command(event):
    await event.respond("""**Bantuan Perintah Pinfairy Bot** 🧚\n
`.p <link>` - Mengunduh satu foto.
`.pv <link>` - Mengunduh satu video.
`.pboard <link_board>` - Mengunduh semua foto dari board.
`.search <query>` - Mencari pin di Pinterest.
`.alive` - Cek status dan info sistem bot.
`.stats` - Melihat statistik bot.
`.help` - Menampilkan pesan ini.""", buttons=Button.inline("🗑️ Tutup", data=f"close_help:0"))
async def process_stats_command(event):
    stats = get_stats(); await event.respond(f"📊 **Statistik Bot**\n\n🖼️ Foto: **{stats.get('photo', 0)}**\n🎬 Video: **{stats.get('video', 0)}**\n🗂️ Board: **{stats.get('board', 0)}**")
async def _send_media_with_buttons(event, data, media_type):
    sent_message = await event.client.send_file(event.chat_id, file=data.get("media_url"), caption=f"✅ {media_type.capitalize()} berhasil diunduh!", reply_to=event.message)
    increment_stat(media_type); message_id = sent_message.id
    await sent_message.edit(buttons=[[Button.url("🔗 Lihat Post Asli", data.get("post_url"))], [Button.inline("ℹ️ Info", data=f"info_msg:{message_id}"), Button.inline("🗑️ Hapus", data=f"delete_confirmation:{message_id}")]])
async def process_pinterest_photo(event, url: str):
    msg = await event.respond("⏳ Mencari foto..."); data = await get_pinterest_photo_data(url)
    if not data.get("is_success"): return await msg.edit(f"⚠️ {data.get('message')}")
    await msg.delete(); await _send_media_with_buttons(event, data, "photo")
async def process_pinterest_video(event, url: str):
    msg = await event.respond("⏳ Mencari video..."); data = await get_pinterest_video_data(url)
    if not data.get("is_success"): return await msg.edit(f"⚠️ {data.get('message')}")
    await msg.delete(); await _send_media_with_buttons(event, data, "video")
async def process_pboard_callback(event):
    try:
        mode = event.data.decode().split('_')[1]; button_message = await event.get_message(); original_cmd_msg = await button_message.get_reply_message()
        if not original_cmd_msg or not original_cmd_msg.text: return await event.answer("Gagal membaca perintah asli.", alert=True)
        url_match = URL_PATTERN.search(original_cmd_msg.text)
        if not url_match: return await event.answer("Tidak dapat menemukan URL di perintah asli.", alert=True)
        url = url_match.group(0); await process_pinterest_board(event, url, mode=mode)
    except Exception as e: logger.error(f"Error di process_pboard_callback: {e}", exc_info=True); await event.edit("❌ **Error!** Terjadi kesalahan.")
async def process_main_callback(event):
    callback_data = event.data.decode("utf-8");
    try: action, target_id_str = callback_data.split(":", 1); target_id = int(target_id_str)
    except ValueError: action, target_id = callback_data, None
    if action == "close_help": return await event.delete()
    if not target_id: return await event.answer()
    if action == "info_msg":
        try:
            msg = await event.client.get_messages(event.chat_id, ids=target_id)
            if not msg or not msg.media: return await event.answer("Media tidak ditemukan.", alert=True)
            file_size = 0; dimensions = "N/A"
            if msg.photo:
                photo_size_info = max(msg.photo.sizes, key=lambda s: s.size); file_size = photo_size_info.size; dimensions = f"{photo_size_info.w} x {photo_size_info.h}"
            elif msg.document:
                file_size = msg.document.size
                for attr in msg.document.attributes:
                    if hasattr(attr, 'w') and hasattr(attr, 'h'): dimensions = f"{attr.w} x {attr.h}"; break
            info_text = (f"--- ℹ️ Info Media ---\n"
                         f"Ukuran File: {humanbytes(file_size)}\n"
                         f"Dimensi: {dimensions}"); return await event.answer(info_text, alert=True)
        except Exception as e: logger.error(f"Gagal menampilkan info: {e}"); return await event.answer("Gagal mendapatkan info media.", alert=True)
    elif action == "delete_confirmation":
        await event.edit("Anda yakin?", buttons=[Button.inline("✅ Ya", data=f"delete_execute:{target_id}"), Button.inline("❌ Batal", data=f"delete_cancel:{target_id}")])
    elif action == "delete_execute": await event.client.delete_messages(event.chat_id, target_id); await event.delete()
    elif action == "delete_cancel":
        try:
            msg = await event.client.get_messages(event.chat_id, ids=target_id)
            original_buttons = [[Button.url("🔗 Lihat Post Asli", msg.buttons[0][0].url)], [Button.inline("ℹ️ Info", data=f"info_msg:{target_id}"), Button.inline("🗑️ Hapus", data=f"delete_confirmation:{target_id}")]]
            await event.edit(buttons=original_buttons)
        except Exception: await event.answer("Gagal membatalkan.")
async def clean_temp_files(folder=DOWNLOADS_DIR, max_age_hours=1):
    if not os.path.isdir(folder): os.makedirs(folder, exist_ok=True); return
    now = time.time(); max_age_seconds = max_age_hours * 3600
    for f in glob.glob(os.path.join(folder, '*')):
        try:
            if now - os.path.getmtime(f) > max_age_seconds:
                if os.path.isdir(f): shutil.rmtree(f)
                else: os.remove(f)
        except Exception as e: logger.error(f"Gagal menghapus item {f}: {e}")