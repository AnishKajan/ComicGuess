#!/usr/bin/env python3
"""
Automated image processing workflow for ComicGuess.
Handles image uploads, optimization, and CDN cache invalidation.
"""

import asyncio
import logging
import json
import os
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

# Storage imports - configure for your preferred storage solution
try:
    # Example: Firebase Storage, AWS S3, or other cloud storage
    # from firebase_admin import storage
    # from google.cloud import storage
    pass
except ImportError:
    print("Storage SDK not installed.")
    print("Install your preferred storage SDK")
    exit(1)

# Cloudflare imports
try:
    import requests
except ImportError:
    print("Requests library not installed.")
    print("Install with: pip install requests")
    exit(1)

# Import our image optimizer
try:
    from image_optimizer import ImageOptimizer, ImageOptimizationResult
except ImportError:
    print("image_optimizer.py not found in the same directory")
    exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ImageProcessingJob:
    """Image processing job configuration."""
    source_path: str
    universe: str  # marvel, DC, image
    character_name: str
    is_primary: bool = True
    metadata: Dict[str, Any] = None

@dataclass
class ProcessingResult:
    """Result of image processing workflow."""
    job: ImageProcessingJob
    original_blob_url: str
    optimized_blob_url: str
    webp_blob_url: str
    avif_blob_url: Optional[str]
    optimization_result: ImageOptimizationResult
    cdn_cache_purged: bool
    processing_time_seconds: float
    error: Optional[str] = None

class CloudflareCache:
    """Cloudflare cache management utility."""
    
    def __init__(self, zone_id: str, api_token: str):
        self.zone_id = zone_id
        self.api_token = api_token
        self.base_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}"
        self.headers = {
            'Authorization': f'Bearer {api_token}',
            'Content-Type': 'application/json'
        }
    
    def purge_cache_by_urls(self, urls: List[str]) -> bool:
        """
        Purge Cloudflare cache for specific URLs.
        
        Args:
            urls: List of URLs to purge from cache
            
        Returns:
            True if successful, False otherwise
        """
        try:
            purge_data = {
                'files': urls
            }
            
            response = requests.post(
                f"{self.base_url}/purge_cache",
                headers=self.headers,
                json=purge_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"Successfully purged {len(urls)} URLs from Cloudflare cache")
                    return True
                else:
                    logger.error(f"Cloudflare cache purge failed: {result.get('errors')}")
                    return False
            else:
                logger.error(f"Cloudflare API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error purging Cloudflare cache: {e}")
            return False
    
    def purge_cache_by_tags(self, tags: List[str]) -> bool:
        """
        Purge Cloudflare cache by cache tags.
        
        Args:
            tags: List of cache tags to purge
            
        Returns:
            True if successful, False otherwise
        """
        try:
            purge_data = {
                'tags': tags
            }
            
            response = requests.post(
                f"{self.base_url}/purge_cache",
                headers=self.headers,
                json=purge_data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    logger.info(f"Successfully purged cache tags: {tags}")
                    return True
                else:
                    logger.error(f"Cloudflare cache purge failed: {result.get('errors')}")
                    return False
            else:
                logger.error(f"Cloudflare API error: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error purging Cloudflare cache by tags: {e}")
            return False

class ImageProcessingWorkflow:
    """Automated image processing workflow."""
    
    def __init__(self, 
                 storage_connection_string: str,
                 container_name: str,
                 cdn_base_url: str,
                 cloudflare_zone_id: str = None,
                 cloudflare_api_token: str = None):
        """
        Initialize image processing workflow.
        
        Args:
            storage_connection_string: Storage service connection string
            container_name: Storage container name
            cdn_base_url: CDN base URL for images
            cloudflare_zone_id: Cloudflare zone ID (optional)
            cloudflare_api_token: Cloudflare API token (optional)
        """
        # Configure your storage client here
        # self.storage_client = YourStorageClient.from_connection_string(storage_connection_string)
        self.container_name = container_name
        self.cdn_base_url = cdn_base_url.rstrip('/')
        
        # Initialize Cloudflare cache manager if credentials provided
        self.cloudflare = None
        if cloudflare_zone_id and cloudflare_api_token:
            self.cloudflare = CloudflareCache(cloudflare_zone_id, cloudflare_api_token)
        
        # Initialize optimizers for different formats
        self.webp_optimizer = ImageOptimizer(
            target_width=800,
            target_height=600,
            quality=85,
            output_format='WEBP'
        )
        
        self.avif_optimizer = ImageOptimizer(
            target_width=800,
            target_height=600,
            quality=85,
            output_format='AVIF'  # Next-gen format
        )
    
    def generate_blob_paths(self, job: ImageProcessingJob) -> Dict[str, str]:
        """
        Generate blob storage paths for different image formats.
        
        Args:
            job: Image processing job
            
        Returns:
            Dictionary of format -> blob path
        """
        # Sanitize character name for file path
        safe_name = "".join(c for c in job.character_name if c.isalnum() or c in (' ', '-', '_')).strip()
        safe_name = safe_name.replace(' ', '-').lower()
        
        base_path = f"{job.universe}/{safe_name}"
        
        return {
            'original': f"{base_path}/original.jpg",
            'webp': f"{base_path}/optimized.webp",
            'avif': f"{base_path}/optimized.avif",
            'thumbnail': f"{base_path}/thumbnail.webp"
        }
    
    async def upload_original_image(self, job: ImageProcessingJob, blob_path: str) -> str:
        """
        Upload original image to blob storage.
        
        Args:
            job: Image processing job
            blob_path: Blob storage path
            
        Returns:
            Blob URL
        """
        try:
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=blob_path
            )
            
            # Set content settings
            content_settings = ContentSettings(
                content_type='image/jpeg',
                cache_control='public, max-age=31536000',  # 1 year cache
                content_disposition=f'inline; filename="{job.character_name}.jpg"'
            )
            
            # Upload file
            with open(job.source_path, 'rb') as data:
                blob_client.upload_blob(
                    data,
                    overwrite=True,
                    content_settings=content_settings,
                    metadata={
                        'universe': job.universe,
                        'character': job.character_name,
                        'is_primary': str(job.is_primary),
                        'upload_date': datetime.utcnow().isoformat(),
                        **(job.metadata or {})
                    }
                )
            
            return blob_client.url
            
        except Exception as e:
            logger.error(f"Error uploading original image: {e}")
            raise
    
    async def create_optimized_versions(self, 
                                      source_blob_path: str, 
                                      target_paths: Dict[str, str]) -> Dict[str, ImageOptimizationResult]:
        """
        Create optimized versions of an image.
        
        Args:
            source_blob_path: Source blob path
            target_paths: Dictionary of format -> target blob path
            
        Returns:
            Dictionary of format -> optimization result
        """
        results = {}
        
        try:
            # Download source image to temporary file
            source_blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name,
                blob=source_blob_path
            )
            
            temp_dir = Path("temp_processing")
            temp_dir.mkdir(exist_ok=True)
            
            temp_source = temp_dir / f"source_{datetime.now().timestamp()}.jpg"
            
            # Download source
            with open(temp_source, 'wb') as f:
                download_stream = source_blob_client.download_blob()
                f.write(download_stream.readall())
            
            # Create WebP version
            if 'webp' in target_paths:
                temp_webp = temp_dir / f"webp_{datetime.now().timestamp()}.webp"
                webp_result = self.webp_optimizer.optimize_single_image(str(temp_source), str(temp_webp))
                
                if not webp_result.error:
                    # Upload WebP version
                    webp_blob_client = self.blob_service_client.get_blob_client(
                        container=self.container_name,
                        blob=target_paths['webp']
                    )
                    
                    content_settings = ContentSettings(
                        content_type='image/webp',
                        cache_control='public, max-age=31536000'
                    )
                    
                    with open(temp_webp, 'rb') as f:
                        webp_blob_client.upload_blob(
                            f,
                            overwrite=True,
                            content_settings=content_settings
                        )
                    
                    webp_result.optimized_path = target_paths['webp']
                
                results['webp'] = webp_result
                
                # Cleanup
                if temp_webp.exists():
                    temp_webp.unlink()
            
            # Create AVIF version (if supported)
            if 'avif' in target_paths:
                try:
                    temp_avif = temp_dir / f"avif_{datetime.now().timestamp()}.avif"
                    avif_result = self.avif_optimizer.optimize_single_image(str(temp_source), str(temp_avif))
                    
                    if not avif_result.error:
                        # Upload AVIF version
                        avif_blob_client = self.blob_service_client.get_blob_client(
                            container=self.container_name,
                            blob=target_paths['avif']
                        )
                        
                        content_settings = ContentSettings(
                            content_type='image/avif',
                            cache_control='public, max-age=31536000'
                        )
                        
                        with open(temp_avif, 'rb') as f:
                            avif_blob_client.upload_blob(
                                f,
                                overwrite=True,
                                content_settings=content_settings
                            )
                        
                        avif_result.optimized_path = target_paths['avif']
                    
                    results['avif'] = avif_result
                    
                    # Cleanup
                    if temp_avif.exists():
                        temp_avif.unlink()
                        
                except Exception as e:
                    logger.warning(f"AVIF optimization failed (may not be supported): {e}")
            
            # Create thumbnail
            if 'thumbnail' in target_paths:
                thumbnail_optimizer = ImageOptimizer(
                    target_width=200,
                    target_height=150,
                    quality=80,
                    output_format='WEBP'
                )
                
                temp_thumb = temp_dir / f"thumb_{datetime.now().timestamp()}.webp"
                thumb_result = thumbnail_optimizer.optimize_single_image(str(temp_source), str(temp_thumb))
                
                if not thumb_result.error:
                    # Upload thumbnail
                    thumb_blob_client = self.blob_service_client.get_blob_client(
                        container=self.container_name,
                        blob=target_paths['thumbnail']
                    )
                    
                    content_settings = ContentSettings(
                        content_type='image/webp',
                        cache_control='public, max-age=31536000'
                    )
                    
                    with open(temp_thumb, 'rb') as f:
                        thumb_blob_client.upload_blob(
                            f,
                            overwrite=True,
                            content_settings=content_settings
                        )
                    
                    thumb_result.optimized_path = target_paths['thumbnail']
                
                results['thumbnail'] = thumb_result
                
                # Cleanup
                if temp_thumb.exists():
                    temp_thumb.unlink()
            
            # Cleanup source
            if temp_source.exists():
                temp_source.unlink()
            
            return results
            
        except Exception as e:
            logger.error(f"Error creating optimized versions: {e}")
            raise
    
    async def process_image(self, job: ImageProcessingJob) -> ProcessingResult:
        """
        Process a single image through the complete workflow.
        
        Args:
            job: Image processing job
            
        Returns:
            Processing result
        """
        start_time = datetime.now()
        
        try:
            # Generate blob paths
            blob_paths = self.generate_blob_paths(job)
            
            # Upload original image
            logger.info(f"Uploading original image for {job.character_name}")
            original_url = await self.upload_original_image(job, blob_paths['original'])
            
            # Create optimized versions
            logger.info(f"Creating optimized versions for {job.character_name}")
            optimization_results = await self.create_optimized_versions(
                blob_paths['original'],
                blob_paths
            )
            
            # Generate CDN URLs
            webp_url = f"{self.cdn_base_url}/{blob_paths['webp']}"
            avif_url = f"{self.cdn_base_url}/{blob_paths['avif']}" if 'avif' in optimization_results else None
            
            # Purge CDN cache if Cloudflare is configured
            cdn_cache_purged = False
            if self.cloudflare:
                urls_to_purge = [
                    f"{self.cdn_base_url}/{blob_paths['original']}",
                    webp_url
                ]
                if avif_url:
                    urls_to_purge.append(avif_url)
                
                cdn_cache_purged = self.cloudflare.purge_cache_by_urls(urls_to_purge)
                
                # Also purge by tags
                cache_tags = [f"universe:{job.universe}", f"character:{job.character_name}"]
                self.cloudflare.purge_cache_by_tags(cache_tags)
            
            processing_time = (datetime.now() - start_time).total_seconds()
            
            return ProcessingResult(
                job=job,
                original_blob_url=original_url,
                optimized_blob_url=webp_url,
                webp_blob_url=webp_url,
                avif_blob_url=avif_url,
                optimization_result=optimization_results.get('webp'),
                cdn_cache_purged=cdn_cache_purged,
                processing_time_seconds=processing_time
            )
            
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error processing image for {job.character_name}: {e}")
            
            return ProcessingResult(
                job=job,
                original_blob_url="",
                optimized_blob_url="",
                webp_blob_url="",
                avif_blob_url=None,
                optimization_result=None,
                cdn_cache_purged=False,
                processing_time_seconds=processing_time,
                error=str(e)
            )
    
    async def batch_process_images(self, jobs: List[ImageProcessingJob]) -> List[ProcessingResult]:
        """
        Process multiple images concurrently.
        
        Args:
            jobs: List of image processing jobs
            
        Returns:
            List of processing results
        """
        logger.info(f"Starting batch processing of {len(jobs)} images")
        
        # Limit concurrency to avoid overwhelming the system
        semaphore = asyncio.Semaphore(3)
        
        async def process_with_semaphore(job):
            async with semaphore:
                return await self.process_image(job)
        
        tasks = [process_with_semaphore(job) for job in jobs]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter out exceptions and log them
        valid_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Error processing job {i}: {result}")
            else:
                valid_results.append(result)
        
        return valid_results

async def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Process images for ComicGuess')
    parser.add_argument('--config', required=True, help='Configuration JSON file')
    parser.add_argument('--jobs', required=True, help='Image processing jobs JSON file')
    
    args = parser.parse_args()
    
    # Load configuration
    with open(args.config, 'r') as f:
        config = json.load(f)
    
    # Load jobs
    with open(args.jobs, 'r') as f:
        jobs_data = json.load(f)
    
    jobs = [ImageProcessingJob(**job_data) for job_data in jobs_data]
    
    # Initialize workflow
    workflow = ImageProcessingWorkflow(
        storage_connection_string=config['storage_connection_string'],
        container_name=config['storage_container'],
        cdn_base_url=config['cdn_base_url'],
        cloudflare_zone_id=config.get('cloudflare_zone_id'),
        cloudflare_api_token=config.get('cloudflare_api_token')
    )
    
    # Process images
    results = await workflow.batch_process_images(jobs)
    
    # Save results
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    results_file = f"image_processing_results_{timestamp}.json"
    
    with open(results_file, 'w') as f:
        json.dump([asdict(result) for result in results], f, indent=2, default=str)
    
    # Print summary
    successful_results = [r for r in results if not r.error]
    total_processing_time = sum(r.processing_time_seconds for r in results)
    
    print(f"\nImage Processing Summary:")
    print(f"Jobs processed: {len(results)}")
    print(f"Successful: {len(successful_results)}")
    print(f"Failed: {len(results) - len(successful_results)}")
    print(f"Total processing time: {total_processing_time:.1f} seconds")
    print(f"Results saved to: {results_file}")

if __name__ == "__main__":
    asyncio.run(main())