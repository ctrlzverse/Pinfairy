"""
Enhanced Pinterest service for Pinfairy Bot
Provides robust Pinterest API interactions with retry mechanisms, caching, and error handling
"""

import asyncio
import httpx
import json
import re
import time
from typing import Dict, List, Optional, Any, Tuple
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page
from urllib.parse import quote_plus

from constants import (
    PINTEREST_HEADERS, PINTEREST_API_ENDPOINT, PINTEREST_SEARCH_ENDPOINT,
    MAX_RETRY_ATTEMPTS, RETRY_DELAY_BASE, CONNECTION_TIMEOUT, READ_TIMEOUT,
    URL_PATTERNS, QUALITY_SETTINGS, MIN_IMAGE_RESOLUTION, BROWSER_CONFIG
)
from exceptions import (
    PinterestAPIException, InvalidURLException, DeadLinkException,
    MediaProcessingException, BrowserException
)
from utils.logger import get_logger
from services.database import db_service

logger = get_logger(__name__)

class RetryMixin:
    """Mixin class for retry functionality with exponential backoff"""
    
    @staticmethod
    async def retry_with_backoff(func, *args, max_retries: int = MAX_RETRY_ATTEMPTS, 
                               base_delay: float = RETRY_DELAY_BASE, **kwargs):
        """Execute function with exponential backoff retry"""
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                if attempt == max_retries - 1:
                    break
                
                delay = base_delay * (2 ** attempt)
                logger.warning(f"Attempt {attempt + 1} failed: {str(e)}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
        
        raise last_exception

class BrowserManager:
    """Manages browser instances for Pinterest scraping"""
    
    def __init__(self):
        self._browser: Optional[Browser] = None
        self._playwright = None
        self.browserless_token = None
        
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def initialize(self):
        """Initialize browser instance"""
        try:
            import os
            self.browserless_token = os.getenv("BROWSERLESS_TOKEN")
            
            self._playwright = await async_playwright().start()
            
            if self.browserless_token:
                logger.info("Connecting to remote browser via browserless.io")
                endpoint = f"wss://chrome.browserless.io?token={self.browserless_token}"
                self._browser = await self._playwright.chromium.connect_over_cdp(endpoint)
            else:
                logger.info("Launching local browser")
                self._browser = await self._playwright.chromium.launch(
                    headless=BROWSER_CONFIG["headless"]
                )
                
        except Exception as e:
            logger.error(f"Failed to initialize browser: {str(e)}", exc_info=True)
            raise BrowserException(f"Browser initialization failed: {str(e)}")
    
    async def create_page(self) -> Page:
        """Create a new browser page with optimized settings"""
        if not self._browser:
            await self.initialize()
        
        page = await self._browser.new_page(
            viewport=BROWSER_CONFIG["viewport"],
            user_agent=BROWSER_CONFIG["user_agent"]
        )
        
        # Block unnecessary resources for faster loading
        await page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2}", lambda route: route.abort())
        
        return page
    
    async def close(self):
        """Close browser and playwright"""
        try:
            if self._browser:
                await self._browser.close()
            if self._playwright:
                await self._playwright.stop()
        except Exception as e:
            logger.error(f"Error closing browser: {str(e)}")

class PinterestService(RetryMixin):
    """Enhanced Pinterest service with comprehensive functionality"""
    
    def __init__(self):
        self.session: Optional[httpx.AsyncClient] = None
        self._cache_enabled = True
    
    async def __aenter__(self):
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def initialize(self):
        """Initialize HTTP session"""
        self.session = httpx.AsyncClient(
            headers=PINTEREST_HEADERS,
            timeout=httpx.Timeout(CONNECTION_TIMEOUT, read=READ_TIMEOUT),
            follow_redirects=True,
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
    
    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.aclose()
    
    async def _get_cached_data(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """Get cached data if available"""
        if not self._cache_enabled:
            return None
        
        try:
            return await db_service.get_cache(cache_key)
        except Exception as e:
            logger.warning(f"Cache retrieval failed: {str(e)}")
            return None
    
    async def _set_cached_data(self, cache_key: str, data: Dict[str, Any], ttl: int = 1800):
        """Set cached data"""
        if not self._cache_enabled:
            return
        
        try:
            await db_service.set_cache(cache_key, data, ttl)
        except Exception as e:
            logger.warning(f"Cache storage failed: {str(e)}")
    
    def _extract_image_url(self, pin_data: Dict[str, Any]) -> Optional[str]:
        """Extract the highest quality image URL from pin data"""
        if not isinstance(pin_data, dict) or not pin_data.get('images'):
            return None
        
        images = pin_data['images']
        
        # Priority order for image quality
        quality_order = ['orig', 'originals', '736x', '564x', '474x', '236x']
        
        for quality in quality_order:
            if quality in images and isinstance(images[quality], dict):
                url = images[quality].get('url')
                if url:
                    return url
        
        # Fallback to any available image
        for key, image_data in images.items():
            if isinstance(image_data, dict) and 'url' in image_data:
                return image_data['url']
        
        return None
    
    def _find_best_video_url(self, data: Dict[str, Any]) -> Optional[str]:
        """Find the best quality video URL from Pinterest data"""
        videos_found = []
        
        def _recursive_search(item):
            if isinstance(item, dict):
                if 'url' in item and isinstance(item['url'], str):
                    url = item['url']
                    if url.endswith('.mp4'):
                        priority = 2
                    elif '.m3u8' in url:
                        priority = 1
                    else:
                        priority = 0
                    
                    if priority > 0:
                        height = item.get('height', 0)
                        if isinstance(height, int):
                            videos_found.append({
                                'url': url, 
                                'height': height, 
                                'priority': priority
                            })
                
                for value in item.values():
                    _recursive_search(value)
            elif isinstance(item, list):
                for i in item:
                    _recursive_search(i)
        
        _recursive_search(data)
        
        if not videos_found:
            return None
        
        # Sort by priority (mp4 > m3u8) then by height (higher = better)
        videos_found.sort(key=lambda x: (x['priority'], x['height']), reverse=True)
        return videos_found[0]['url']
    
    def _clean_and_deduplicate_urls(self, urls: List[str], min_resolution: int = MIN_IMAGE_RESOLUTION) -> List[str]:
        """Clean URLs and remove duplicates while maintaining quality"""
        seen_images = {}
        
        for url in urls:
            if not url.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                continue
            
            # Convert to original resolution
            orig_url = re.sub(r'/\d+x\d+/', '/originals/', url)
            
            # Extract base filename for duplicate detection
            base_filename = orig_url.split('/')[-1].split('?')[0]
            
            # Get resolution for quality filtering
            resolution_match = re.search(URL_PATTERNS["image_resolution"], url)
            if resolution_match:
                width, height = map(int, resolution_match.groups())
                resolution = width * height
                if resolution < min_resolution:
                    continue
            
            # Keep highest quality version of each unique image
            if base_filename not in seen_images:
                seen_images[base_filename] = orig_url
        
        return list(seen_images.values())
    
    async def get_photo_data(self, url: str) -> Dict[str, Any]:
        """Get Pinterest photo data with caching and retry"""
        cache_key = f"photo_data:{url}"
        
        # Check cache first
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            logger.info(f"Retrieved photo data from cache for {url}")
            return cached_data
        
        async def _fetch_photo():
            start_time = time.time()
            
            try:
                response = await self.session.get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                meta_tag = soup.find('meta', {'property': 'og:image'})
                
                if not meta_tag or not meta_tag.get('content'):
                    raise MediaProcessingException("Photo metadata not found")
                
                image_url = meta_tag['content']
                # Convert to highest quality
                image_url = image_url.replace('/236x/', '/originals/').replace('/736x/', '/originals/')
                
                result = {
                    "is_success": True,
                    "media_url": image_url,
                    "post_url": url,
                    "media_type": "photo"
                }
                
                # Cache the result
                await self._set_cached_data(cache_key, result)
                
                duration = time.time() - start_time
                logger.info(f"Successfully fetched photo data in {duration:.2f}s", 
                           url=url, duration=duration)
                
                return result
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise DeadLinkException("Photo not found or deleted")
                raise PinterestAPIException(f"HTTP error: {e.response.status_code}")
            except Exception as e:
                raise MediaProcessingException(f"Failed to process photo: {str(e)}")
        
        return await self.retry_with_backoff(_fetch_photo)
    
    async def get_video_data(self, url: str) -> Dict[str, Any]:
        """Get Pinterest video data with enhanced error handling"""
        cache_key = f"video_data:{url}"
        
        # Check cache first
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            logger.info(f"Retrieved video data from cache for {url}")
            return cached_data
        
        async def _fetch_video():
            start_time = time.time()
            
            try:
                response = await self.session.get(url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                json_script = soup.find('script', {'data-relay-response': 'true'})
                
                if not json_script:
                    raise MediaProcessingException("Video data script not found")
                
                data = json.loads(json_script.string)
                video_url = self._find_best_video_url(data)
                
                if not video_url:
                    raise MediaProcessingException("No video URL found in data")
                
                result = {
                    "is_success": True,
                    "media_url": video_url,
                    "post_url": url,
                    "media_type": "video"
                }
                
                # Cache the result
                await self._set_cached_data(cache_key, result)
                
                duration = time.time() - start_time
                logger.info(f"Successfully fetched video data in {duration:.2f}s", 
                           url=url, duration=duration)
                
                return result
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise DeadLinkException("Video not found or deleted")
                raise PinterestAPIException(f"HTTP error: {e.response.status_code}")
            except json.JSONDecodeError:
                raise MediaProcessingException("Invalid JSON in video data")
            except Exception as e:
                raise MediaProcessingException(f"Failed to process video: {str(e)}")
        
        return await self.retry_with_backoff(_fetch_video)
    
    async def get_board_pins(self, board_url: str, max_pins: int = 500) -> Dict[str, Any]:
        """Get all pins from a Pinterest board with pagination"""
        cache_key = f"board_pins:{board_url}:{max_pins}"
        
        # Check cache first
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            logger.info(f"Retrieved board data from cache for {board_url}")
            return cached_data
        
        async def _fetch_board():
            start_time = time.time()
            all_image_urls = set()
            
            try:
                # First, try HTTP scraping
                response = await self.session.get(board_url)
                response.raise_for_status()
                html_content = response.text
                
                # Extract initial images
                initial_urls = re.findall(URL_PATTERNS["pinterest_image"], html_content)
                cleaned_urls = self._clean_and_deduplicate_urls(initial_urls)
                all_image_urls.update(cleaned_urls)
                
                # Try API pagination
                board_id_match = re.search(URL_PATTERNS["board_id"], html_content)
                bookmark_match = re.search(URL_PATTERNS["bookmark"], html_content)
                
                if board_id_match and bookmark_match:
                    board_id = board_id_match.group(1)
                    bookmark = bookmark_match.group(1)
                    
                    # Paginate through API
                    page_count = 0
                    max_pages = max_pins // 50  # 50 pins per page
                    
                    while bookmark and bookmark != '-end-' and page_count < max_pages:
                        await asyncio.sleep(1)  # Rate limiting
                        
                        payload = {
                            "options": {
                                "board_id": board_id,
                                "page_size": 50,
                                "bookmarks": [bookmark]
                            }
                        }
                        
                        api_response = await self.session.get(
                            PINTEREST_API_ENDPOINT,
                            params={
                                'source_url': board_url,
                                'data': json.dumps(payload)
                            }
                        )
                        
                        if api_response.status_code != 200:
                            logger.warning(f"API request failed: {api_response.status_code}")
                            break
                        
                        api_data = api_response.json()
                        pins = api_data.get('resource_response', {}).get('data', [])
                        
                        for pin in pins:
                            image_url = self._extract_image_url(pin)
                            if image_url:
                                orig_url = re.sub(r'/\d+x\d+/', '/originals/', image_url)
                                all_image_urls.add(orig_url)
                        
                        bookmark = api_data.get('resource_response', {}).get('bookmark')
                        page_count += 1
                
                # Fallback to browser scraping if needed
                if len(all_image_urls) < 10:
                    logger.info("Falling back to browser scraping for board")
                    browser_urls = await self._scrape_board_with_browser(board_url)
                    all_image_urls.update(browser_urls)
                
                if not all_image_urls:
                    raise MediaProcessingException("No images found in board")
                
                result = {
                    "is_success": True,
                    "image_urls": list(all_image_urls)[:max_pins],
                    "board_url": board_url,
                    "total_found": len(all_image_urls)
                }
                
                # Cache the result
                await self._set_cached_data(cache_key, result, ttl=3600)  # 1 hour cache
                
                duration = time.time() - start_time
                logger.info(f"Successfully fetched {len(all_image_urls)} pins in {duration:.2f}s", 
                           url=board_url, duration=duration)
                
                return result
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise DeadLinkException("Board not found or private")
                raise PinterestAPIException(f"HTTP error: {e.response.status_code}")
            except Exception as e:
                raise MediaProcessingException(f"Failed to fetch board: {str(e)}")
        
        return await self.retry_with_backoff(_fetch_board)
    
    async def _scrape_board_with_browser(self, board_url: str) -> List[str]:
        """Scrape board using browser automation as fallback"""
        try:
            async with BrowserManager() as browser_manager:
                page = await browser_manager.create_page()
                
                await page.goto(board_url, wait_until="domcontentloaded", timeout=60000)
                
                # Scroll to load more pins
                for _ in range(10):
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(2000)
                
                await page.wait_for_load_state("networkidle", timeout=30000)
                html_content = await page.content()
                
                found_urls = re.findall(URL_PATTERNS["pinterest_image"], html_content)
                return self._clean_and_deduplicate_urls(found_urls)
                
        except Exception as e:
            logger.error(f"Browser scraping failed: {str(e)}", exc_info=True)
            raise BrowserException(f"Browser scraping failed: {str(e)}")
    
    async def search_pins(self, query: str, limit: int = 20) -> Dict[str, Any]:
        """Search for Pinterest pins"""
        cache_key = f"search_pins:{query}:{limit}"
        
        # Check cache first
        cached_data = await self._get_cached_data(cache_key)
        if cached_data:
            logger.info(f"Retrieved search results from cache for query: {query}")
            return cached_data
        
        async def _search():
            start_time = time.time()
            
            try:
                search_url = f"{PINTEREST_SEARCH_ENDPOINT}?q={quote_plus(query)}"
                
                async with BrowserManager() as browser_manager:
                    page = await browser_manager.create_page()
                    
                    await page.goto(search_url, timeout=60000)
                    await page.wait_for_selector('[data-test-id="pin-visual-wrapper"]', timeout=30000)
                    
                    # Scroll to load more results
                    for _ in range(3):
                        await page.evaluate("window.scrollBy(0, 1000)")
                        await page.wait_for_timeout(2000)
                    
                    html_content = await page.content()
                
                # Extract image URLs
                found_urls = re.findall(URL_PATTERNS["pinterest_image"], html_content)
                cleaned_urls = self._clean_and_deduplicate_urls(found_urls)
                
                if not cleaned_urls:
                    raise MediaProcessingException("No search results found")
                
                results = [{"url": url} for url in cleaned_urls[:limit]]
                
                result = {
                    "is_success": True,
                    "pins": results,
                    "query": query,
                    "total_found": len(results)
                }
                
                # Cache the result
                await self._set_cached_data(cache_key, result, ttl=1800)  # 30 minutes cache
                
                duration = time.time() - start_time
                logger.info(f"Search completed in {duration:.2f}s for query: {query}", 
                           duration=duration)
                
                return result
                
            except Exception as e:
                raise MediaProcessingException(f"Search failed: {str(e)}")
        
        return await self.retry_with_backoff(_search)

# Global Pinterest service instance
pinterest_service = PinterestService()

# Convenience functions for backward compatibility
async def get_pinterest_photo_data(url: str) -> Dict[str, Any]:
    """Get Pinterest photo data"""
    async with pinterest_service:
        return await pinterest_service.get_photo_data(url)

async def get_pinterest_video_data(url: str) -> Dict[str, Any]:
    """Get Pinterest video data"""
    async with pinterest_service:
        return await pinterest_service.get_video_data(url)

async def get_all_pins_with_pagination(board_url: str) -> Dict[str, Any]:
    """Get all pins from board"""
    async with pinterest_service:
        return await pinterest_service.get_board_pins(board_url)

async def search_pins(query: str, limit: int = 20) -> Dict[str, Any]:
    """Search Pinterest pins"""
    async with pinterest_service:
        return await pinterest_service.search_pins(query, limit)