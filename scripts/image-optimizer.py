#!/usr/bin/env python3
"""
Image optimization pipeline for ComicGuess character images.
Optimizes images for web delivery with EXIF stripping, resizing, and format conversion.
"""

import os
import sys
import logging
import asyncio
import aiofiles
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json

# Image processing imports
try:
    from PIL import Image, ImageOps
    from PIL.ExifTags import TAGS
    import pillow_heif  # For HEIF/HEIC support
except ImportError:
    print("Required image processing libraries not installed.")
    print("Install with: pip install Pillow pillow-heif")
    sys.exit(1)

# Cloud Storage imports - configure for your preferred storage solution
try:
    # Example: Firebase Storage, AWS S3, or other cloud storage
    # from firebase_admin import storage
    # from google.cloud import storage
    pass
except ImportError:
    print("Storage SDK not installed.")
    print("Install your preferred storage SDK")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class ImageOptimizationResult:
    """Result of image optimization process."""
    original_path: str
    optimized_path: str
    original_size_bytes: int
    optimized_size_bytes: int
    compression_ratio: float
    format_original: str
    format_optimized: str
    dimensions_original: Tuple[int, int]
    dimensions_optimized: Tuple[int, int]
    exif_stripped: bool
    processing_time_seconds: float
    error: Optional[str] = None

class ImageOptimizer:
    """Image optimization utility for ComicGuess character images."""
    
    def __init__(self, 
                 target_width: int = 800,
                 target_height: int = 600,
                 quality: int = 85,
                 output_format: str = 'WEBP'):
        """
        Initialize image optimizer.
        
        Args:
            target_width: Maximum width for optimized images
            target_height: Maximum height for optimized images
            quality: JPEG/WebP quality (1-100)
            output_format: Output format (WEBP, JPEG, PNG)
        """
        self.target_width = target_width
        self.target_height = target_height
        self.quality = quality
        self.output_format = output_format.upper()
        
        # Register HEIF opener
        pillow_heif.register_heif_opener()
        
        # Supported input formats
        self.supported_formats = {
            'JPEG', 'JPG', 'PNG', 'WEBP', 'BMP', 'TIFF', 'HEIC', 'HEIF'
        }
    
    def strip_exif_data(self, image: Image.Image) -> Tuple[Image.Image, bool]:
        """
        Strip EXIF data from image for privacy and size reduction.
        
        Args:
            image: PIL Image object
            
        Returns:
            Tuple of (cleaned image, exif_was_present)
        """
        try:
            # Check if image has EXIF data
            exif_present = hasattr(image, '_getexif') and image._getexif() is not None
            
            # Create new image without EXIF data
            if exif_present:
                # Convert to RGB if necessary and create new image
                if image.mode in ('RGBA', 'LA', 'P'):
                    # Preserve transparency for formats that support it
                    if self.output_format in ('PNG', 'WEBP'):
                        cleaned_image = image.convert('RGBA')
                    else:
                        # Create white background for formats without transparency
                        background = Image.new('RGB', image.size, (255, 255, 255))
                        if image.mode == 'P':
                            image = image.convert('RGBA')
                        background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                        cleaned_image = background
                else:
                    cleaned_image = image.convert('RGB')
                
                return cleaned_image, True
            else:
                return image, False
                
        except Exception as e:
            logger.warning(f"Error stripping EXIF data: {e}")
            return image, False
    
    def resize_image(self, image: Image.Image) -> Image.Image:
        """
        Resize image while maintaining aspect ratio.
        
        Args:
            image: PIL Image object
            
        Returns:
            Resized image
        """
        original_width, original_height = image.size
        
        # Calculate new dimensions maintaining aspect ratio
        aspect_ratio = original_width / original_height
        
        if aspect_ratio > (self.target_width / self.target_height):
            # Width is the limiting factor
            new_width = min(self.target_width, original_width)
            new_height = int(new_width / aspect_ratio)
        else:
            # Height is the limiting factor
            new_height = min(self.target_height, original_height)
            new_width = int(new_height * aspect_ratio)
        
        # Only resize if the image is larger than target
        if new_width < original_width or new_height < original_height:
            # Use high-quality resampling
            resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            return resized_image
        
        return image
    
    def optimize_single_image(self, input_path: str, output_path: str) -> ImageOptimizationResult:
        """
        Optimize a single image file.
        
        Args:
            input_path: Path to input image
            output_path: Path for optimized output
            
        Returns:
            ImageOptimizationResult with optimization details
        """
        start_time = datetime.now()
        
        try:
            # Get original file size
            original_size = os.path.getsize(input_path)
            
            # Open and process image
            with Image.open(input_path) as image:
                original_format = image.format
                original_dimensions = image.size
                
                # Strip EXIF data
                cleaned_image, exif_stripped = self.strip_exif_data(image)
                
                # Resize image
                resized_image = self.resize_image(cleaned_image)
                
                # Optimize and save
                save_kwargs = {
                    'format': self.output_format,
                    'optimize': True
                }
                
                if self.output_format in ('JPEG', 'WEBP'):
                    save_kwargs['quality'] = self.quality
                elif self.output_format == 'PNG':
                    save_kwargs['compress_level'] = 6  # Good compression without too much CPU
                
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Save optimized image
                resized_image.save(output_path, **save_kwargs)
                
                # Get optimized file size
                optimized_size = os.path.getsize(output_path)
                compression_ratio = (original_size - optimized_size) / original_size * 100
                
                processing_time = (datetime.now() - start_time).total_seconds()
                
                return ImageOptimizationResult(
                    original_path=input_path,
                    optimized_path=output_path,
                    original_size_bytes=original_size,
                    optimized_size_bytes=optimized_size,
                    compression_ratio=compression_ratio,
                    format_original=original_format,
                    format_optimized=self.output_format,
                    dimensions_original=original_dimensions,
                    dimensions_optimized=resized_image.size,
                    exif_stripped=exif_stripped,
                    processing_time_seconds=processing_time
                )
                
        except Exception as e:
            processing_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Error optimizing image {input_path}: {e}")
            
            return ImageOptimizationResult(
                original_path=input_path,
                optimized_path=output_path,
                original_size_bytes=0,
                optimized_size_bytes=0,
                compression_ratio=0,
                format_original='UNKNOWN',
                format_optimized=self.output_format,
                dimensions_original=(0, 0),
                dimensions_optimized=(0, 0),
                exif_stripped=False,
                processing_time_seconds=processing_time,
                error=str(e)
            )
    
    def batch_optimize_directory(self, input_dir: str, output_dir: str) -> List[ImageOptimizationResult]:
        """
        Optimize all images in a directory.
        
        Args:
            input_dir: Directory containing input images
            output_dir: Directory for optimized outputs
            
        Returns:
            List of optimization results
        """
        results = []
        input_path = Path(input_dir)
        
        if not input_path.exists():
            logger.error(f"Input directory does not exist: {input_dir}")
            return results
        
        # Find all image files
        image_files = []
        for ext in self.supported_formats:
            image_files.extend(input_path.rglob(f"*.{ext.lower()}"))
            image_files.extend(input_path.rglob(f"*.{ext.upper()}"))
        
        logger.info(f"Found {len(image_files)} images to optimize")
        
        for image_file in image_files:
            # Maintain directory structure in output
            relative_path = image_file.relative_to(input_path)
            output_file = Path(output_dir) / relative_path.with_suffix(f'.{self.output_format.lower()}')
            
            result = self.optimize_single_image(str(image_file), str(output_file))
            results.append(result)
            
            if result.error:
                logger.error(f"Failed to optimize {image_file}: {result.error}")
            else:
                logger.info(f"Optimized {image_file.name}: {result.compression_ratio:.1f}% size reduction")
        
        return results

class CloudStorageImageOptimizer:
    """Cloud Storage integration for image optimization."""
    
    def __init__(self, connection_string: str, container_name: str):
        """
        Initialize Cloud Storage image optimizer.
        
        Args:
            connection_string: Storage service connection string
            container_name: Storage container name
        """
        self.blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        self.container_name = container_name
        self.optimizer = ImageOptimizer()
    
    async def optimize_blob_image(self, blob_name: str, optimized_blob_name: str = None) -> ImageOptimizationResult:
        """
        Download, optimize, and re-upload a blob image.
        
        Args:
            blob_name: Name of the blob to optimize
            optimized_blob_name: Name for optimized blob (optional)
            
        Returns:
            ImageOptimizationResult
        """
        if optimized_blob_name is None:
            # Generate optimized blob name
            path_parts = blob_name.split('/')
            filename = path_parts[-1]
            name, _ = os.path.splitext(filename)
            optimized_filename = f"{name}_optimized.webp"
            path_parts[-1] = optimized_filename
            optimized_blob_name = '/'.join(path_parts)
        
        try:
            # Download original blob
            blob_client = self.blob_service_client.get_blob_client(
                container=self.container_name, 
                blob=blob_name
            )
            
            # Create temporary files
            temp_dir = Path("temp_image_optimization")
            temp_dir.mkdir(exist_ok=True)
            
            temp_input = temp_dir / f"input_{datetime.now().timestamp()}"
            temp_output = temp_dir / f"output_{datetime.now().timestamp()}.webp"
            
            # Download blob to temporary file
            async with aiofiles.open(temp_input, 'wb') as f:
                download_stream = blob_client.download_blob()
                async for chunk in download_stream.chunks():
                    await f.write(chunk)
            
            # Optimize image
            result = self.optimizer.optimize_single_image(str(temp_input), str(temp_output))
            
            if not result.error:
                # Upload optimized image
                optimized_blob_client = self.blob_service_client.get_blob_client(
                    container=self.container_name,
                    blob=optimized_blob_name
                )
                
                # Set appropriate content type
                content_settings = ContentSettings(
                    content_type='image/webp',
                    cache_control='public, max-age=31536000'  # 1 year cache
                )
                
                async with aiofiles.open(temp_output, 'rb') as f:
                    content = await f.read()
                    optimized_blob_client.upload_blob(
                        content,
                        overwrite=True,
                        content_settings=content_settings
                    )
                
                result.optimized_path = optimized_blob_name
            
            # Cleanup temporary files
            if temp_input.exists():
                temp_input.unlink()
            if temp_output.exists():
                temp_output.unlink()
            
            return result
            
        except Exception as e:
            logger.error(f"Error optimizing blob {blob_name}: {e}")
            return ImageOptimizationResult(
                original_path=blob_name,
                optimized_path=optimized_blob_name,
                original_size_bytes=0,
                optimized_size_bytes=0,
                compression_ratio=0,
                format_original='UNKNOWN',
                format_optimized='WEBP',
                dimensions_original=(0, 0),
                dimensions_optimized=(0, 0),
                exif_stripped=False,
                processing_time_seconds=0,
                error=str(e)
            )
    
    async def batch_optimize_container(self, prefix: str = "") -> List[ImageOptimizationResult]:
        """
        Optimize all images in a container with optional prefix filter.
        
        Args:
            prefix: Blob name prefix filter
            
        Returns:
            List of optimization results
        """
        results = []
        
        try:
            container_client = self.blob_service_client.get_container_client(self.container_name)
            blob_list = container_client.list_blobs(name_starts_with=prefix)
            
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.heic', '.heif'}
            image_blobs = [
                blob for blob in blob_list
                if any(blob.name.lower().endswith(ext) for ext in image_extensions)
            ]
            
            logger.info(f"Found {len(image_blobs)} images to optimize in container")
            
            # Process images concurrently (but limit concurrency)
            semaphore = asyncio.Semaphore(5)  # Max 5 concurrent optimizations
            
            async def optimize_with_semaphore(blob):
                async with semaphore:
                    return await self.optimize_blob_image(blob.name)
            
            tasks = [optimize_with_semaphore(blob) for blob in image_blobs]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter out exceptions and log them
            valid_results = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Error processing blob {image_blobs[i].name}: {result}")
                else:
                    valid_results.append(result)
            
            return valid_results
            
        except Exception as e:
            logger.error(f"Error batch optimizing container: {e}")
            return results

def main():
    """Main function for command-line usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Optimize images for ComicGuess')
    parser.add_argument('--input-dir', help='Input directory containing images')
    parser.add_argument('--output-dir', help='Output directory for optimized images')
    parser.add_argument('--storage-connection', help='Storage service connection string')
    parser.add_argument('--container', help='Storage container name')
    parser.add_argument('--blob-prefix', help='Blob name prefix filter', default='')
    parser.add_argument('--width', type=int, default=800, help='Target width')
    parser.add_argument('--height', type=int, default=600, help='Target height')
    parser.add_argument('--quality', type=int, default=85, help='Output quality (1-100)')
    parser.add_argument('--format', default='WEBP', help='Output format (WEBP, JPEG, PNG)')
    
    args = parser.parse_args()
    
    if args.input_dir and args.output_dir:
        # Local directory optimization
        optimizer = ImageOptimizer(
            target_width=args.width,
            target_height=args.height,
            quality=args.quality,
            output_format=args.format
        )
        
        results = optimizer.batch_optimize_directory(args.input_dir, args.output_dir)
        
        # Print summary
        total_original_size = sum(r.original_size_bytes for r in results if not r.error)
        total_optimized_size = sum(r.optimized_size_bytes for r in results if not r.error)
        total_savings = total_original_size - total_optimized_size
        avg_compression = (total_savings / total_original_size * 100) if total_original_size > 0 else 0
        
        print(f"\nOptimization Summary:")
        print(f"Images processed: {len(results)}")
        print(f"Total size reduction: {total_savings / 1024 / 1024:.1f} MB")
        print(f"Average compression: {avg_compression:.1f}%")
        
        # Save detailed results
        results_file = f"image_optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump([result.__dict__ for result in results], f, indent=2, default=str)
        print(f"Detailed results saved to: {results_file}")
        
    elif args.storage_connection and args.container:
        # Cloud Storage optimization
        async def run_storage_optimization():
            storage_optimizer = CloudStorageImageOptimizer(args.storage_connection, args.container)
            results = await storage_optimizer.batch_optimize_container(args.blob_prefix)
            
            # Print summary
            successful_results = [r for r in results if not r.error]
            total_original_size = sum(r.original_size_bytes for r in successful_results)
            total_optimized_size = sum(r.optimized_size_bytes for r in successful_results)
            total_savings = total_original_size - total_optimized_size
            avg_compression = (total_savings / total_original_size * 100) if total_original_size > 0 else 0
            
            print(f"\nCloud Storage Optimization Summary:")
            print(f"Images processed: {len(successful_results)}")
            print(f"Total size reduction: {total_savings / 1024 / 1024:.1f} MB")
            print(f"Average compression: {avg_compression:.1f}%")
            
            # Save results
            results_file = f"storage_optimization_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(results_file, 'w') as f:
                json.dump([result.__dict__ for result in results], f, indent=2, default=str)
            print(f"Detailed results saved to: {results_file}")
        
        asyncio.run(run_storage_optimization())
        
    else:
        parser.print_help()
        print("\nExamples:")
        print("  Local optimization:")
        print("    python image-optimizer.py --input-dir ./images --output-dir ./optimized")
        print("  Cloud Storage optimization:")
        print("    python image-optimizer.py --storage-connection 'connection_string' --container 'images'")

if __name__ == "__main__":
    main()