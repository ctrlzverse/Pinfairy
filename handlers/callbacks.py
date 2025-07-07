import logging
from core import process_pboard_callback, process_main_callback, update_user_settings, process_auto_download, process_start_callback, process_leaderboard_callback, process_feedback_callback, process_admin_callback

logger = logging.getLogger(__name__)

async def handle_button_press(event):
    """
    Satu handler untuk semua tombol. Bertindak sebagai router
    yang memanggil fungsi proses yang sesuai dari core.
    """
    button_data = event.data.decode("utf-8")
    logger.info(f"Callback diterima dari user {event.sender_id} dengan data: {button_data}")

    # Router logic
    if button_data.startswith("auto_"):
        await process_auto_download(event)
    elif button_data.startswith("pboard_"):
        await process_pboard_callback(event)
    elif button_data.startswith("config_"):
        await handle_config_callback(event)
    elif button_data in ["refresh_leaderboard", "my_stats"]:
        await process_leaderboard_callback(event)
    elif button_data in ["feedback_input", "feature_request_input"]:
        await process_feedback_callback(event)
    elif button_data in ["do_backup", "do_restore"]:
        await process_admin_callback(event)
    elif button_data in ["quick_guide", "full_help", "back_to_start"]:
        await process_start_callback(event)
    else:
        await process_main_callback(event)

async def handle_config_callback(event):
    """Handle configuration button callbacks."""
    callback_data = event.data.decode("utf-8")
    user_id = event.sender_id
    
    try:
        if callback_data == "config_language":
            from telethon.tl.custom import Button
            await event.edit(
                "🌐 **Pilih Bahasa:**",
                buttons=[
                    [Button.inline("🇮🇩 Indonesia", data="set_lang_id")],
                    [Button.inline("🇺🇸 English", data="set_lang_en")],
                    [Button.inline("🔙 Kembali", data="config_back")]
                ]
            )
        
        elif callback_data == "config_notifications":
            from telethon.tl.custom import Button
            await event.edit(
                "🔔 **Pengaturan Notifikasi:**",
                buttons=[
                    [Button.inline("✅ Aktifkan", data="set_notif_on")],
                    [Button.inline("❌ Nonaktifkan", data="set_notif_off")],
                    [Button.inline("🔙 Kembali", data="config_back")]
                ]
            )
        
        elif callback_data == "config_quality":
            from telethon.tl.custom import Button
            await event.edit(
                "🎨 **Kualitas Download:**",
                buttons=[
                    [Button.inline("🔥 High", data="set_quality_high")],
                    [Button.inline("⚡ Medium", data="set_quality_medium")],
                    [Button.inline("💾 Low", data="set_quality_low")],
                    [Button.inline("🔙 Kembali", data="config_back")]
                ]
            )
        
        elif callback_data == "config_reset":
            from core import DEFAULT_SETTINGS
            update_user_settings(user_id, DEFAULT_SETTINGS)
            await event.answer("✅ Pengaturan telah direset ke default!", alert=True)
            await event.edit("⚙️ **Pengaturan telah direset!**\n\nGunakan `.config` untuk melihat pengaturan baru.")
        
        elif callback_data == "config_close":
            await event.delete()
        
        elif callback_data == "config_back":
            from core import process_config_command
            await process_config_command(event)
        
        # Language settings
        elif callback_data.startswith("set_lang_"):
            lang = callback_data.split("_")[-1]
            update_user_settings(user_id, {"language": lang})
            lang_name = "Indonesia" if lang == "id" else "English"
            await event.answer(f"✅ Bahasa diubah ke {lang_name}!", alert=True)
            from core import process_config_command
            await process_config_command(event)
        
        # Notification settings
        elif callback_data.startswith("set_notif_"):
            notif = callback_data.split("_")[-1] == "on"
            update_user_settings(user_id, {"notifications": notif})
            status = "diaktifkan" if notif else "dinonaktifkan"
            await event.answer(f"✅ Notifikasi {status}!", alert=True)
            from core import process_config_command
            await process_config_command(event)
        
        # Quality settings
        elif callback_data.startswith("set_quality_"):
            quality = callback_data.split("_")[-1]
            update_user_settings(user_id, {"download_quality": quality})
            await event.answer(f"✅ Kualitas diubah ke {quality.title()}!", alert=True)
            from core import process_config_command
            await process_config_command(event)
            
    except Exception as e:
        logger.error(f"Error in config callback: {e}", exc_info=True)
        await event.answer("❌ Terjadi kesalahan!", alert=True)
