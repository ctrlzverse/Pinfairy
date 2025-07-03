import logging
from core import process_pboard_callback, process_main_callback

logger = logging.getLogger(__name__)

async def handle_button_press(event):
    """
    Satu handler untuk semua tombol. Bertindak sebagai router
    yang memanggil fungsi proses yang sesuai dari core.
    """
    button_data = event.data.decode("utf-8")
    logger.info(f"Callback diterima dari user {event.sender_id} dengan data: {button_data}")

    # Router logic
    if button_data.startswith("pboard_"):
        await process_pboard_callback(event)
    else:
        await process_main_callback(event)