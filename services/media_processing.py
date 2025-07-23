"""
Media processing service for Pinfairy Bot
Handles file operations, format conversion, and media optimization
"""

import os
import asyncio
import aiofiles
import hashlib
import mimetypes
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import zipfile
import tempfile
import shutil
from datetime import datetime

from constants import (
    DOWNLOADS_DIR, IMAGE_FORMATS, VIDEO_FORMATS, MAX_FILE_SIZE,
    QUALITY_SETTINGS
)
from exceptions import MediaProcessingException
from utils.logger import get_logger

logger = get_logger(__name__)

class FileManager:
    """Manages file operations and cleanup"""
    
    def __init__(self):
        self.temp_dirs = set()
        self.temp_files = set()
    
    async def create_temp_dir(self, prefix: str = "pinfairy_") -> str:
        """Create temporary directory"""
        temp_dir = tempfile.mkdtemp(prefix=prefix)
        self.temp_dirs.add(temp_dir)
        return temp_dir
    
    async def create_temp_file(self, suffix: str = "", prefix: str = "pinfairy_") -> str:
        """Create temporary file"""
        fd, temp_file = tempfile.mkstemp(suffix=suffix, prefix=prefix)
        os.close(fd)  # Close file descriptor
        self.temp_files.add(temp_file)
        return temp_file
    
    async def ensure_dir_exists(self, directory: str):
        """Ensure directory exists"""
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    async def cleanup_temp_files(self):
        """Clean up all temporary files and directories"""
        # Clean up temporary files
        for temp_file in list(self.temp_files):
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                self.temp_files.discard(temp_file)
            except Exception as e:
                logger.warning(f"Failed to remove temp file {temp_file}: {str(e)}")
        
        # Clean up temporary directories
        for temp_dir in list(self.temp_dirs):
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                self.temp_dirs.discard(temp_dir)
            except Exception as e:
                logger.warning(f"Failed to remove temp dir {temp_dir}: {str(e)}")
    
    def get_file_info(self, file_path: str) -> Dict[str, Any]:
        """Get file information"""
        try:
            stat = os.stat(file_path)
            mime_type, _ = mimetypes.guess_type(file_path)
            
            return {
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime),
                "mime_type": mime_type,
                "extension": Path(file_path).suffix.lower(),
                "filename": Path(file_path).name
            }
        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {str(e)}")
            return {}

class MediaProcessor:
    """Processes media files with optimization and conversion"""
    
    def __init__(self):
        self.file_manager = FileManager()
    
    async def download_file(self, url: str, destination: str = None, 
                           progress_callback=None) -> Dict[str, Any]:
        """Download file from URL with progress tracking"""
        import httpx
        
        try:
            if not destination:
                destination = await self.file_manager.create_temp_file(
                    suffix=self._get_extension_from_url(url)
                )
            
            async with httpx.AsyncClient() as client:
                async with client.stream('GET', url) as response:
                    response.raise_for_status()
                    
                    total_size = int(response.headers.get('content-length', 0))
                    downloaded = 0
                    
                    async with aiofiles.open(destination, 'wb') as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            await f.write(chunk)
                            downloaded += len(chunk)
                            
                            if progress_callback and total_size > 0:
                                progress = (downloaded / total_size) * 100
                                await progress_callback(downloaded, total_size, progress)
            
            file_info = self.file_manager.get_file_info(destination)
            
            return {
                "success": True,
                "file_path": destination,
                "file_info": file_info
            }
            
        except Exception as e:
            logger.error(f"Failed to download file from {url}: {str(e)}", exc_info=True)
            raise MediaProcessingException(f"Download failed: {str(e)}")
    
    async def create_zip_archive(self, files: List[str], archive_name: str,
                                progress_callback=None) -> str:
        """Create ZIP archive from list of files"""
        try:
            await self.file_manager.ensure_dir_exists(DOWNLOADS_DIR)
            zip_path = os.path.join(DOWNLOADS_DIR, f"{archive_name}.zip")
            
            total_files = len(files)
            processed = 0
            
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
                for file_path in files:
                    if os.path.exists(file_path):
                        # Use just the filename in the archive
                        arcname = os.path.basename(file_path)
                        zf.write(file_path, arcname=arcname)
                        processed += 1
                        
                        if progress_callback:
                            progress = (processed / total_files) * 100
                            await progress_callback(processed, total_files, progress)
            
            if processed == 0:
                raise MediaProcessingException("No files were added to archive")
            
            logger.info(f"Created ZIP archive with {processed} files: {zip_path}")
            return zip_path
            
        except Exception as e:
            logger.error(f"Failed to create ZIP archive: {str(e)}", exc_info=True)
            raise MediaProcessingException(f"Archive creation failed: {str(e)}")
    
    async def optimize_image(self, image_path: str, quality: str = "high") -> str:
        """Optimize image based on quality setting"""
        try:
            # For now, just return the original path
            # In a full implementation, you could use PIL/Pillow for optimization
            return image_path
            
        except Exception as e:
            logger.error(f"Failed to optimize image {image_path}: {str(e)}", exc_info=True)
            raise MediaProcessingException(f"Image optimization failed: {str(e)}")
    
    async def get_image_metadata(self, image_path: str) -> Dict[str, Any]:
        """Extract image metadata"""
        try:
            # Basic file info
            file_info = self.file_manager.get_file_info(image_path)
            
            # For a full implementation, you could use PIL/Pillow or exifread
            # to extract EXIF data, dimensions, etc.
            
            return {
                "file_info": file_info,
                "dimensions": None,  # Would extract actual dimensions
                "exif": None,  # Would extract EXIF data
                "color_profile": None  # Would extract color profile
            }
            
        except Exception as e:
            logger.error(f"Failed to get image metadata for {image_path}: {str(e)}")
            return {"error": str(e)}
    
    async def batch_download(self, urls: List[str], destination_dir: str = None,
                           progress_callback=None) -> Dict[str, Any]:
        """Download multiple files concurrently"""
        try:
            if not destination_dir:
                destination_dir = await self.file_manager.create_temp_dir()
            else:
                await self.file_manager.ensure_dir_exists(destination_dir)
            
            total_urls = len(urls)
            completed = 0
            successful_downloads = []
            failed_downloads = []
            
            async def download_single(url: str, index: int):
                nonlocal completed
                try:
                    filename = f"{index+1:04d}{self._get_extension_from_url(url)}"
                    destination = os.path.join(destination_dir, filename)
                    
                    result = await self.download_file(url, destination)
                    successful_downloads.append({
                        "url": url,
                        "file_path": result["file_path"],
                        "file_info": result["file_info"]
                    })
                    
                except Exception as e:
                    failed_downloads.append({
                        "url": url,
                        "error": str(e)
                    })
                
                completed += 1
                if progress_callback:
                    progress = (completed / total_urls) * 100
                    await progress_callback(completed, total_urls, progress)
            
            # Download files concurrently with limited concurrency
            semaphore = asyncio.Semaphore(5)  # Limit to 5 concurrent downloads
            
            async def download_with_semaphore(url: str, index: int):
                async with semaphore:
                    await download_single(url, index)
            
            tasks = [download_with_semaphore(url, i) for i, url in enumerate(urls)]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            return {
                "success": True,
                "destination_dir": destination_dir,
                "successful_downloads": successful_downloads,
                "failed_downloads": failed_downloads,
                "total_successful": len(successful_downloads),
                "total_failed": len(failed_downloads)
            }
            
        except Exception as e:
            logger.error(f"Batch download failed: {str(e)}", exc_info=True)
            raise MediaProcessingException(f"Batch download failed: {str(e)}")
    
    def _get_extension_from_url(self, url: str) -> str:
        """Extract file extension from URL"""
        try:
            # Remove query parameters
            url = url.split('?')[0]
            extension = Path(url).suffix.lower()
            
            # Default to .jpg if no extension found
            if not extension or extension not in IMAGE_FORMATS + VIDEO_FORMATS:
                extension = '.jpg'
            
            return extension
        except:
            return '.jpg'
    
    def _generate_filename(self, prefix: str = "", suffix: str = "") -> str:
        """Generate unique filename"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        random_hash = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
        return f"{prefix}{timestamp}_{random_hash}{suffix}"
    
    async def cleanup(self):
        """Clean up temporary files"""
        await self.file_manager.cleanup_temp_files()

class ProgressTracker:
    """Tracks progress for long-running operations"""
    
    def __init__(self, total: int, operation: str = "Processing"):
        self.total = total
        self.current = 0
        self.operation = operation
        self.start_time = datetime.now()
        self.callbacks = []
    
    def add_callback(self, callback):
        """Add progress callback"""
        self.callbacks.append(callback)
    
    async def update(self, increment: int = 1):
        """Update progress"""
        self.current += increment
        progress_percent = (self.current / self.total) * 100 if self.total > 0 else 0
        
        elapsed = (datetime.now() - self.start_time).total_seconds()
        eta = (elapsed / self.current * (self.total - self.current)) if self.current > 0 else 0
        
        progress_data = {
            "current": self.current,
            "total": self.total,
            "percent": progress_percent,
            "elapsed": elapsed,
            "eta": eta,
            "operation": self.operation
        }
        
        # Call all registered callbacks
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(progress_data)
                else:
                    callback(progress_data)
            except Exception as e:
                logger.warning(f"Progress callback failed: {str(e)}")
    
    def is_complete(self) -> bool:
        """Check if operation is complete"""
        return self.current >= self.total

# Global media processor instance
media_processor = MediaProcessor()

# Convenience functions
async def download_file(url: str, destination: str = None, progress_callback=None):
    """Download single file"""
    return await media_processor.download_file(url, destination, progress_callback)

async def batch_download(urls: List[str], destination_dir: str = None, progress_callback=None):
    """Download multiple files"""
    return await media_processor.batch_download(urls, destination_dir, progress_callback)

async def create_zip_archive(files: List[str], archive_name: str, progress_callback=None):
    """Create ZIP archive"""
    return await media_processor.create_zip_archive(files, archive_name, progress_callback)

async def cleanup_temp_files():
    """Clean up temporary files"""
    await media_processor.cleanup()