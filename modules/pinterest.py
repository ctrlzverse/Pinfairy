import logging
import httpx
from bs4 import BeautifulSoup
import json
import re
import asyncio
import os
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BROWSERLESS_TOKEN = os.getenv("BROWSERLESS_TOKEN")

async def _get_browser():
    """Connect to a remote browser if a token is available, otherwise launch a local one."""
    p = await async_playwright().start()
    if BROWSERLESS_TOKEN:
        logger.info("Connecting to remote browser via browserless.io...")
        endpoint = f"wss://chrome.browserless.io?token={BROWSERLESS_TOKEN}"
        return await p.chromium.connect_over_cdp(endpoint)
    else:
        logger.info("Launching local browser...")
        return await p.chromium.launch()

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.5',
}

def _extract_image_url(pin_data: dict) -> str | None:
    if not isinstance(pin_data, dict) or not pin_data.get('images'): return None
    if image_url := pin_data['images'].get('orig', {}).get('url'): return image_url
    if key := next(iter(pin_data['images']), None): return pin_data['images'][key].get('url')
    return None

async def get_all_pins_with_pagination(board_url: str) -> dict:
    board_url = board_url.strip().rstrip("`")
    logger.info(f"[Pinterest] Mulai scraping board: {board_url}")
    all_image_urls = {}  # Dictionary untuk menyimpan URL dengan resolusi tertinggi
    PINTEREST_API_ENDPOINT = "https://www.pinterest.com/resource/BoardFeedResource/get/"
    
    MIN_RESOLUTION = 200 * 200  # Minimum resolution threshold to filter low-quality images
    
    def get_image_resolution(url: str) -> int:
        """Extract resolution from Pinterest URL."""
        match = re.search(r'/(\d+)x(\d+)/', url)
        if match:
            width, height = map(int, match.groups())
            return width * height
        return 0
    
    def get_original_url(url: str) -> str:
        """Convert URL to highest resolution."""
        return re.sub(r'/\d+x\d+/', '/originals/', url)
    
    def is_duplicate_image(url1: str, url2: str) -> bool:
        """Check if two URLs point to the same image."""
        # Extract base filename without resolution
        base1 = re.sub(r'/\d+x\d+/', '/', url1).split('/')[-1]
        base2 = re.sub(r'/\d+x\d+/', '/', url2).split('/')[-1]
        return base1 == base2
    
    try:
        async with httpx.AsyncClient(headers=HEADERS, timeout=45.0, follow_redirects=True) as client:
            response = await client.get(board_url)
            response.raise_for_status()
            html_content = response.text
            
            # Find all image URLs
            initial_urls = re.findall(r'https://i\.pinimg\.com/[^\s"\']+', html_content)
            logger.debug(f"[Pinterest] Ditemukan {len(initial_urls)} gambar dari HTML awal.")
            
            # Process initial URLs
            for url in initial_urls:
                if url.endswith(('.jpg', '.jpeg', '.png')):
                    # Convert to original resolution
                    orig_url = get_original_url(url)
                    resolution = get_image_resolution(orig_url)
                    if resolution < MIN_RESOLUTION:
                        continue  # Skip low-quality images
                    
                    # Check for duplicates
                    is_duplicate = False
                    for existing_url in list(all_image_urls.keys()):
                        if is_duplicate_image(orig_url, existing_url):
                            is_duplicate = True
                            break
                    
                    if not is_duplicate:
                        all_image_urls[orig_url] = True
            board_id_match = re.search(r'"board_id":\s*"(\d+)"', html_content)
            bookmark_match = re.search(r'"bookmarks":\s*\["([^\"]+)"\]', html_content)
            
            if not board_id_match or not bookmark_match:
                logger.warning(f"[Pinterest] Board ID atau bookmark tidak ditemukan. Board mungkin private/kosong/format berubah.")
                if all_image_urls:
                    return {"is_success": True, "image_urls": list(all_image_urls.keys())}
                
                # Fallback ke Playwright jika scraping manual gagal
                logger.info("[Pinterest] Fallback ke Playwright untuk scraping board.")
                try:
                    browser = await _get_browser()
                    page = await browser.new_page()
                    await page.goto(board_url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Scroll down multiple times to load all pins
                    for _ in range(10):
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        await page.wait_for_timeout(2000)  # Wait for content to load
                    
                    await page.wait_for_load_state("networkidle", timeout=30000)
                    html_content = await page.content()
                    await browser.close()
                    
                    found_urls = re.findall(r'https://i\.pinimg\.com/[^\s"\']+', html_content)
                    logger.debug(f"[Pinterest] Playwright menemukan {len(found_urls)} gambar di board.")
                    
                    # Process Playwright URLs with deduplication and filtering
                    processed_urls = {}
                    for url in found_urls:
                        if url.endswith(('.jpg', '.jpeg', '.png')):
                            orig_url = get_original_url(url)
                            resolution = get_image_resolution(orig_url)
                            if resolution < MIN_RESOLUTION:
                                continue  # Skip low-quality images
                            is_duplicate = False
                            for existing_url in list(processed_urls.keys()):
                                if is_duplicate_image(orig_url, existing_url):
                                    is_duplicate = True
                                    break
                            if not is_duplicate:
                                processed_urls[orig_url] = True
                    
                    if processed_urls:
                        return {"is_success": True, "image_urls": list(processed_urls.keys()), "fallback": "playwright"}
                    else:
                        return {"is_success": False, "message": "Board kosong/private/format berubah. Tidak ada gambar ditemukan (Playwright)."}
                except Exception as e:
                    logger.error(f"[Pinterest] Fallback Playwright gagal: {e}", exc_info=True)
                    return {"is_success": False, "message": f"Gagal scraping board (Playwright): {e}"}
            
            board_id = board_id_match.group(1)
            bookmark = bookmark_match.group(1)
            
            # API pagination with deduplication and increased page size
            while bookmark and bookmark != '-end-':
                await asyncio.sleep(1)
                payload = {"options": {"board_id": board_id, "page_size": 50, "bookmarks": [bookmark]}}
                api_response = await client.get(PINTEREST_API_ENDPOINT, params={'source_url': board_url, 'data': json.dumps(payload)})
                
                if api_response.status_code != 200:
                    logger.warning(f"[Pinterest] API Pinterest gagal: {api_response.status_code}")
                    break
                
                api_data = api_response.json()
                for pin in api_data.get('resource_response', {}).get('data', []):
                    if images := pin.get('images'):
                        # Get highest resolution image
                        best_url = None
                        best_resolution = 0
                        
                        for size_key, image_data in images.items():
                            if isinstance(image_data, dict) and 'url' in image_data:
                                url = image_data['url']
                                resolution = get_image_resolution(url)
                                if resolution > best_resolution:
                                    best_resolution = resolution
                                    best_url = url
                        
                        if best_url:
                            orig_url = get_original_url(best_url)
                            if get_image_resolution(orig_url) < MIN_RESOLUTION:
                                continue  # Skip low-quality images
                            
                            # Check for duplicates
                            is_duplicate = False
                            for existing_url in list(all_image_urls.keys()):
                                if is_duplicate_image(orig_url, existing_url):
                                    is_duplicate = True
                                    break
                            
                            if not is_duplicate:
                                all_image_urls[orig_url] = True
                
                bookmark = api_data.get('resource_response', {}).get('bookmark')
            
            if all_image_urls:
                return {"is_success": True, "image_urls": list(all_image_urls.keys()), "board_url": board_url}
            else:
                logger.warning(f"[Pinterest] Board tidak mengandung gambar setelah pagination.")
                return {"is_success": False, "message": "Board tidak mengandung gambar setelah pagination."}
    except Exception as e:
        logger.error(f"[Pinterest] Terjadi error scraping board: {e}", exc_info=True)
        return {"is_success": False, "message": f"Terjadi kesalahan saat scraping: {e}"}

async def get_pinterest_photo_data(url: str) -> dict:
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True) as client:
            r = await client.get(url); r.raise_for_status(); soup = BeautifulSoup(r.text, 'html.parser')
            meta_tag = soup.find('meta', {'property': 'og:image'})
            if meta_tag and meta_tag.get('content'):
                return {"is_success": True, "media_url": meta_tag['content'].replace('/236x/', '/originals/').replace('/736x/', '/originals/'), "post_url": url}
            return {"is_success": False, "message": "Tidak dapat menemukan data foto."}
    except Exception: return {"is_success": False, "message": "Terjadi kesalahan."}

def find_best_video_url(data):
    """Mencari semua URL video, memprioritaskan .mp4, dan memilih kualitas terbaik."""
    videos_found = []

    def _recursive_hunter(item):
        if isinstance(item, dict):
            if 'url' in item and isinstance(item['url'], str):
                url = item['url']
                if url.endswith('.mp4'):
                    priority = 1
                elif '.m3u8' in url:
                    priority = 0
                else:
                    priority = -1
                
                if priority >= 0:
                    height = item.get('height', 0)
                    if isinstance(height, int):
                        videos_found.append({'url': url, 'height': height, 'priority': priority})

            for value in item.values():
                _recursive_hunter(value)
        elif isinstance(item, list):
            for i in item:
                _recursive_hunter(i)

    _recursive_hunter(data)

    if not videos_found:
        return None

    videos_found.sort(key=lambda x: (x['priority'], x['height']), reverse=True)
    return videos_found[0]['url']


async def get_pinterest_video_data(url: str) -> dict:
    """Fungsi ini HANYA mencari dan mengunduh VIDEO dengan metode httpx (lama)."""
    logger.info(f"Memburu VIDEO dari URL (Metode Lama): {url}")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=HEADERS, follow_redirects=True)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            json_data_script = soup.find('script', {'data-relay-response': 'true'})
            if not json_data_script:
                logger.warning("Script data-relay-response tidak ditemukan.")
                return {"is_success": False, "message": "Format halaman tidak didukung untuk video."}

            data = json.loads(json_data_script.string)

            video_url = find_best_video_url(data)
            
            if video_url:
                logger.info(f"✅ Video .mp4 terbaik ditemukan oleh pemburu: {video_url}")
                return {"is_success": True, "media_url": video_url, "post_url": url}
            else:
                logger.warning("Pemburu tidak menemukan URL video .mp4 yang valid di dalam JSON.")
                return {"is_success": False, "message": "Link ini bukan video atau video tidak dapat diakses."}

    except Exception as e:
        logger.error(f"Error di get_pinterest_video_data: {e}")
        return {"is_success": False, "message": "Terjadi kesalahan saat mengambil data video."}

async def search_pins(query: str, limit: int = 10) -> dict:
    logger.info(f"Memulai pencarian (metode Playwright) untuk query: '{query}'")
    search_url = f"https://www.pinterest.com/search/pins/?q={query}"
    try:
        browser = await _get_browser()
        page = await browser.new_page()
        await page.goto(search_url, timeout=60000)
        await page.wait_for_selector('[data-test-id="pin-visual-wrapper"]', timeout=30000)
        await page.evaluate("window.scrollBy(0, 1000)"); await asyncio.sleep(2)
        html_content = await page.content()
        await browser.close()
        found_urls = re.findall(r'https://i\.pinimg\.com/originals[^\s"]+\.jpg', html_content)
        if not found_urls:
             found_urls.extend(re.findall(r'https://i\.pinimg\.com/736x[^\s"]+\.jpg', html_content))
        if not found_urls:
            return {"is_success": False, "message": "Playwright tidak menemukan URL gambar di halaman."}
        clean_urls = list(dict.fromkeys(found_urls))
        results = [{"url": url} for url in clean_urls[:limit]]
        return {"is_success": True, "pins": results}
    except Exception as e:
        logger.error(f"Error di search_pins (Playwright): {e}", exc_info=True)
        return {"is_success": False, "message": f"Terjadi kesalahan saat scraping dengan Playwright: {e}"}
