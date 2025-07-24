"""
Enhanced Pinterest service for Pinfairy Bot
Provides robust Pinterest API interactions with retry mechanisms, caching, and error handling
"""

import asyncio
import httpx
import json
import re
import time
import hashlib
from typing import Dict, List, Optional, Any, Tuple, Set
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, Page
from urllib.parse import quote_plus
from dataclasses import dataclass
from contextlib import asynccontextmanager

from constants import (
    PINTEREST_HEADERS, PINTEREST_API_ENDPOINT, PINTEREST_SEARCH_ENDPOINT,
    MAX_RETRY_ATTEMPTS, RETRY_DELAY_BASE, CONNECTION_TIMEOUT, READ_TIMEOUT,
    URL_PATTERNS, QUALITY_SETTINGS, MIN_IMAGE_RESOLUTION, BROWSER_CONFIG,
    CACHE_TTL
)
from exceptions import (
    PinterestAPIException, InvalidURLException, DeadLinkException,
    MediaProcessingException, BrowserException
)
from utils.logger import get_logger
from services.database import db_service

logger = get_logger(__name__)

@dataclass
class PinterestMedia:
    """Structured Pinterest media data"""
    url: str
    media_type: str  # 'photo', 'video', 'board'
    title: str = ""
    description: str = ""
    media_url: str = ""
    thumbnail_url: str = ""
    resolution: Tuple[int, int] = (0, 0)
    file_size: int = 0
    quality: str = "high"

class CacheManager:
    """Manages caching for Pinterest data"""

    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_times: Dict[str, float] = {}
        self._max_cache_size = 1000

    def _generate_key(self, url: str, params: Dict = None) -> str:
        """Generate cache key from URL and parameters"""
        key_data = f"{url}_{json.dumps(params, sort_keys=True) if params else ''}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def get(self, url: str, params: Dict = None, ttl: int = CACHE_TTL["pinterest_data"]) -> Optional[Any]:
        """Get cached data if not expired"""
        key = self._generate_key(url, params)

        if key in self._cache:
            if time.time() - self._cache_times[key] < ttl:
                logger.debug(f"Cache hit for {url[:50]}...")
                return self._cache[key]
            else:
                # Expired
                del self._cache[key]
                del self._cache_times[key]

        return None

    def set(self, url: str, data: Any, params: Dict = None):
        """Cache data with size management"""
        key = self._generate_key(url, params)

        # Manage cache size
        if len(self._cache) >= self._max_cache_size:
            # Remove oldest entries
            oldest_keys = sorted(self._cache_times.keys(), key=lambda k: self._cache_times[k])[:100]
            for old_key in oldest_keys:
                del self._cache[old_key]
                del self._cache_times[old_key]

        self._cache[key] = data
        self._cache_times[key] = time.time()
        logger.debug(f"Cached data for {url[:50]}...")

    def clear(self):
        """Clear all cached data"""
        self._cache.clear()
        self._cache_times.clear()

class ConnectionPool:
    """HTTP connection pool for Pinterest requests"""

    def __init__(self, max_connections: int = 10):
        self._clients: List[httpx.AsyncClient] = []
        self._max_connections = max_connections
        self._lock = asyncio.Lock()

    async def get_client(self) -> httpx.AsyncClient:
        """Get HTTP client from pool"""
        async with self._lock:
            if self._clients:
                return self._clients.pop()

            # Create new client
            client = httpx.AsyncClient(
                headers=PINTEREST_HEADERS,
                timeout=httpx.Timeout(
                    connect=CONNECTION_TIMEOUT,
                    read=READ_TIMEOUT,
                    write=30.0,
                    pool=60.0
                ),
                limits=httpx.Limits(
                    max_keepalive_connections=20,
                    max_connections=50
                ),
                follow_redirects=True
            )
            return client

    async def return_client(self, client: httpx.AsyncClient):
        """Return client to pool"""
        async with self._lock:
            if len(self._clients) < self._max_connections:
                self._clients.append(client)
            else:
                await client.aclose()

    async def close_all(self):
        """Close all clients in pool"""
        async with self._lock:
            for client in self._clients:
                await client.aclose()
            self._clients.clear()

class RetryMixin:
    """Enhanced retry functionality with exponential backoff and circuit breaker"""

    def __init__(self):
        self._failure_counts: Dict[str, int] = {}
        self._last_failure_times: Dict[str, float] = {}
        self._circuit_breaker_threshold = 5
        self._circuit_breaker_timeout = 300  # 5 minutes

    def _get_circuit_key(self, func_name: str, *args) -> str:
        """Generate circuit breaker key"""
        return f"{func_name}_{hash(str(args))}"

    def _is_circuit_open(self, circuit_key: str) -> bool:
        """Check if circuit breaker is open"""
        if circuit_key not in self._failure_counts:
            return False

        failure_count = self._failure_counts[circuit_key]
        last_failure = self._last_failure_times.get(circuit_key, 0)

        if failure_count >= self._circuit_breaker_threshold:
            if time.time() - last_failure < self._circuit_breaker_timeout:
                return True
            else:
                # Reset circuit breaker
                self._failure_counts[circuit_key] = 0
                return False

        return False

    def _record_failure(self, circuit_key: str):
        """Record failure for circuit breaker"""
        self._failure_counts[circuit_key] = self._failure_counts.get(circuit_key, 0) + 1
        self._last_failure_times[circuit_key] = time.time()

    def _record_success(self, circuit_key: str):
        """Record success for circuit breaker"""
        if circuit_key in self._failure_counts:
            del self._failure_counts[circuit_key]
        if circuit_key in self._last_failure_times:
            del self._last_failure_times[circuit_key]

    async def retry_with_backoff(self, func, *args, max_retries: int = MAX_RETRY_ATTEMPTS,
                               base_delay: float = RETRY_DELAY_BASE, **kwargs):
        """Execute function with exponential backoff retry and circuit breaker"""
        circuit_key = self._get_circuit_key(func.__name__, *args)

        # Check circuit breaker
        if self._is_circuit_open(circuit_key):
            raise PinterestAPIException(f"Circuit breaker open for {func.__name__}")

        last_exception = None

        for attempt in range(max_retries):
            try:
                result = await func(*args, **kwargs)
                self._record_success(circuit_key)
                return result

            except (httpx.ConnectTimeout, httpx.ReadTimeout, httpx.NetworkError) as e:
                last_exception = e
                self._record_failure(circuit_key)

                if attempt == max_retries - 1:
                    break

                delay = min(base_delay * (2 ** attempt), 60)  # Cap at 60 seconds
                logger.warning(f"Network error on attempt {attempt + 1}: {str(e)}. Retrying in {delay}s...")
                await asyncio.sleep(delay)

            except Exception as e:
                # Don't retry on non-network errors
                self._record_failure(circuit_key)
                raise e

        self._record_failure(circuit_key)
        raise last_exception

class BrowserManager:
    """Enhanced browser manager with connection pooling and resource optimization"""

    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._browser: Optional[Browser] = None
        self._playwright = None
        self.browserless_token = None
        self._page_pool: List[Page] = []
        self._max_pages = 3
        self._initialized = False

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self):
        """Initialize browser instance with optimization"""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            try:
                import os
                self.browserless_token = os.getenv("BROWSERLESS_TOKEN")

                self._playwright = await async_playwright().start()

                if self.browserless_token:
                    logger.info("Connecting to remote browser via browserless.io")
                    endpoint = f"wss://chrome.browserless.io?token={self.browserless_token}"
                    self._browser = await self._playwright.chromium.connect_over_cdp(endpoint)
                else:
                    logger.info("Launching local browser with optimizations")
                    self._browser = await self._playwright.chromium.launch(
                        headless=BROWSER_CONFIG["headless"],
                        args=[
                            '--no-sandbox',
                            '--disable-setuid-sandbox',
                            '--disable-dev-shm-usage',
                            '--disable-accelerated-2d-canvas',
                            '--no-first-run',
                            '--no-zygote',
                            '--disable-gpu',
                            '--disable-background-timer-throttling',
                            '--disable-backgrounding-occluded-windows',
                            '--disable-renderer-backgrounding'
                        ]
                    )

                self._initialized = True
                logger.info("Browser initialized successfully")

            except Exception as e:
                logger.error(f"Failed to initialize browser: {str(e)}", exc_info=True)
                raise BrowserException(f"Browser initialization failed: {str(e)}")

    async def get_page(self) -> Page:
        """Get page from pool or create new one"""
        async with self._lock:
            if self._page_pool:
                page = self._page_pool.pop()
                # Check if page is still valid
                try:
                    await page.evaluate("1 + 1")
                    return page
                except Exception:
                    # Page is invalid, create new one
                    pass

        return await self.create_page()

    async def return_page(self, page: Page):
        """Return page to pool"""
        async with self._lock:
            if len(self._page_pool) < self._max_pages:
                try:
                    # Clear page state
                    await page.goto("about:blank")
                    self._page_pool.append(page)
                except Exception:
                    await page.close()
            else:
                await page.close()

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

        # Set optimized timeouts
        page.set_default_timeout(BROWSER_CONFIG["timeout"])
        page.set_default_navigation_timeout(BROWSER_CONFIG["timeout"])

        return page
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
    """Enhanced Pinterest service with comprehensive functionality and optimization"""

    def __init__(self):
        super().__init__()
        self._connection_pool = ConnectionPool(max_connections=10)
        self._cache_manager = CacheManager()
        self._browser_manager = BrowserManager()
        self._rate_limiter = {}
        self._last_request_times = {}
        self._request_count = 0
        self._session_start_time = time.time()

    async def __aenter__(self):
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def initialize(self):
        """Initialize service components"""
        await self._browser_manager.initialize()
        logger.info("Pinterest service initialized")

    async def close(self):
        """Close all service components"""
        await self._connection_pool.close_all()
        await self._browser_manager.close()
        logger.info("Pinterest service closed")

    async def _rate_limit_check(self, endpoint: str):
        """Check and enforce rate limiting"""
        current_time = time.time()

        # Global rate limiting
        if endpoint in self._last_request_times:
            time_since_last = current_time - self._last_request_times[endpoint]
            if time_since_last < 1.0:  # 1 second between requests to same endpoint
                await asyncio.sleep(1.0 - time_since_last)

        self._last_request_times[endpoint] = current_time
        self._request_count += 1

        # Log rate limiting stats
        if self._request_count % 100 == 0:
            session_time = current_time - self._session_start_time
            rate = self._request_count / session_time if session_time > 0 else 0
            logger.info(f"Request rate: {rate:.2f} req/s ({self._request_count} total)")

    async def _make_request(self, url: str, method: str = "GET", **kwargs) -> httpx.Response:
        """Make HTTP request with connection pooling and rate limiting"""
        await self._rate_limit_check(url)

        client = await self._connection_pool.get_client()
        try:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        finally:
            await self._connection_pool.return_client(client)

    def _get_cache_key(self, url: str, params: Dict = None) -> str:
        """Generate cache key for URL and parameters"""
        return self._cache_manager._generate_key(url, params)

    async def _get_cached_data(self, cache_key: str, ttl: int = CACHE_TTL["pinterest_data"]) -> Optional[Dict[str, Any]]:
        """Get cached data with fallback to database cache"""
        # Try memory cache first
        cached = self._cache_manager.get(cache_key, ttl=ttl)
        if cached:
            return cached

        # Try database cache
        try:
            db_cached = await db_service.get_cache(cache_key)
            if db_cached:
                # Store in memory cache for faster access
                self._cache_manager.set(cache_key, db_cached)
                return db_cached
        except Exception as e:
            logger.warning(f"Database cache retrieval failed: {str(e)}")

        return None

    async def _set_cached_data(self, cache_key: str, data: Dict[str, Any], ttl: int = CACHE_TTL["pinterest_data"]):
        """Set cached data in both memory and database"""
        # Store in memory cache
        self._cache_manager.set(cache_key, data)

        # Store in database cache
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