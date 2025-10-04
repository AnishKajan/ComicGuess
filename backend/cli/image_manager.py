#!/usr/bin/env python3
"""
CLI tool for bulk image upload and management.
Supports image validation, optimization, and batch operations.
"""

import asyncio
import argparse
import logging
import mimetypes
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, BinaryIO
from PIL import Image
import hashlib

from app.storage.blob_storage import BlobStorageService
from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageManager:
    """CLI tool for managing character images"""
    
    def __init__(self):
        self.blob_service = BlobStorageService()
        self.supported_formats = {'.jpg', '.jpeg', '.png', '.webp'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.max_dimensions = (2048, 2048)  # Max width/height
    
    async def upload_image(self, universe: str, character_name: str, image_path: Path,
                          optimize: bool = True, overwrite: bool = False) -> Dict[str, Any]:
        """
        Upload a single character image.
        
        Args:
            universe: Comic universe (marvel, DC, image)
            character_name: Character name
            image_path: Path to image file
            optimize: Whether to optimize the image
            overwrite: Whether to overwrite existing image
            
        Returns:
            Upload result with status and details
        """
        result = {
            'success': False,
            'character': character_name,
            'universe': universe,
            'original_size': 0,
            'final_size': 0,
            'blob_path': None,
            'error': None
        }
        
        try:
            # Validate file exists
            if not image_path.exists():
                result['error'] = f"File not found: {image_path}"
                return result
            
            # Validate file format
            if image_path.suffix.lower() not in self.supported_formats:
                result['error'] = f"Unsupported format: {image_path.suffix}"
                return result
            
            # Get original file size
            result['original_size'] = image_path.stat().st_size
            
            # Validate file size
            if result['original_size'] > self.max_file_size:
                result['error'] = f"File too large: {result['original_size']} bytes (max: {self.max_file_size})"
                return result
            
            # Check if image already exists
            existing_url = await self.blob_service.get_image_url(universe, character_name)
            if existing_url and not overwrite:
                result['error'] = f"Image already exists for {character_name} (use --overwrite to replace)"
                return result
            
            # Process image
            if optimize:
                processed_data, content_type = await self._optimize_image(image_path)
            else:
                with open(image_path, 'rb') as f:
                    processed_data = f.read()
                content_type = mimetypes.guess_type(str(image_path))[0] or 'image/jpeg'
            
            result['final_size'] = len(processed_data)
            
            # Upload to blob storage
            from io import BytesIO
            blob_path = await self.blob_service.upload_image(
                universe, character_name, BytesIO(processed_data), content_type
            )
            
            result['success'] = True
            result['blob_path'] = blob_path
            
            logger.info(f"Successfully uploaded {character_name} ({universe}): {result['original_size']} -> {result['final_size']} bytes")
            
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Failed to upload {character_name}: {e}")
        
        return result
    
    async def bulk_upload(self, universe: str, images_dir: Path, 
                         optimize: bool = True, overwrite: bool = False,
                         dry_run: bool = False) -> Dict[str, Any]:
        """
        Upload multiple images from a directory.
        
        Expected directory structure:
        images_dir/
        ├── character-name-1.jpg
        ├── character-name-2.png
        └── ...
        
        Character names are derived from filenames (without extension).
        
        Args:
            universe: Comic universe (marvel, DC, image)
            images_dir: Directory containing images
            optimize: Whether to optimize images
            overwrite: Whether to overwrite existing images
            dry_run: If True, validate but don't upload
            
        Returns:
            Bulk upload statistics
        """
        stats = {
            'total_files': 0,
            'valid_images': 0,
            'invalid_images': 0,
            'uploaded': 0,
            'skipped': 0,
            'errors': [],
            'total_original_size': 0,
            'total_final_size': 0
        }
        
        if not images_dir.exists() or not images_dir.is_dir():
            raise ValueError(f"Directory not found: {images_dir}")
        
        logger.info(f"Starting bulk upload from {images_dir} to {universe} universe")
        
        # Find all image files
        image_files = []
        for ext in self.supported_formats:
            image_files.extend(images_dir.glob(f"*{ext}"))
            image_files.extend(images_dir.glob(f"*{ext.upper()}"))
        
        stats['total_files'] = len(image_files)
        
        if stats['total_files'] == 0:
            logger.warning(f"No image files found in {images_dir}")
            return stats
        
        # Process each image
        for image_path in image_files:
            # Extract character name from filename
            character_name = self._filename_to_character_name(image_path.stem)
            
            try:
                # Validate image
                validation_result = await self._validate_image(image_path)
                if not validation_result['valid']:
                    stats['invalid_images'] += 1
                    stats['errors'].append(f"{image_path.name}: {validation_result['error']}")
                    continue
                
                stats['valid_images'] += 1
                stats['total_original_size'] += image_path.stat().st_size
                
                if dry_run:
                    logger.info(f"Would upload: {character_name} from {image_path.name}")
                    continue
                
                # Upload image
                result = await self.upload_image(
                    universe, character_name, image_path, optimize, overwrite
                )
                
                if result['success']:
                    stats['uploaded'] += 1
                    stats['total_final_size'] += result['final_size']
                else:
                    stats['skipped'] += 1
                    stats['errors'].append(f"{image_path.name}: {result['error']}")
                
            except Exception as e:
                stats['invalid_images'] += 1
                stats['errors'].append(f"{image_path.name}: {str(e)}")
        
        logger.info(f"Bulk upload complete: {stats['uploaded']} uploaded, {stats['skipped']} skipped")
        return stats
    
    async def validate_images(self, universe: Optional[str] = None) -> Dict[str, Any]:
        """
        Validate images in blob storage.
        
        Args:
            universe: Validate specific universe (optional)
            
        Returns:
            Validation results
        """
        results = {
            'total_images': 0,
            'accessible_images': 0,
            'inaccessible_images': 0,
            'errors': []
        }
        
        universes = [universe] if universe else ['marvel', 'DC', 'image']
        
        for univ in universes:
            try:
                character_names = await self.blob_service.list_images_by_universe(univ)
                results['total_images'] += len(character_names)
                
                for character_name in character_names:
                    url = await self.blob_service.get_image_url(univ, character_name)
                    if url:
                        results['accessible_images'] += 1
                    else:
                        results['inaccessible_images'] += 1
                        results['errors'].append(f"Cannot access image for {character_name} in {univ}")
                        
            except Exception as e:
                results['errors'].append(f"Error validating {univ} universe: {str(e)}")
        
        return results
    
    async def list_images(self, universe: str) -> List[str]:
        """
        List all images in a universe.
        
        Args:
            universe: Comic universe
            
        Returns:
            List of character names with images
        """
        return await self.blob_service.list_images_by_universe(universe)
    
    async def delete_image(self, universe: str, character_name: str, confirm: bool = False) -> bool:
        """
        Delete a character image.
        
        Args:
            universe: Comic universe
            character_name: Character name
            confirm: Must be True to actually delete
            
        Returns:
            True if deleted successfully
        """
        if not confirm:
            logger.warning("Delete operation requires confirm=True")
            return False
        
        success = await self.blob_service.delete_image(universe, character_name)
        if success:
            logger.info(f"Deleted image for {character_name} in {universe} universe")
        
        return success
    
    async def _optimize_image(self, image_path: Path) -> tuple[bytes, str]:
        """
        Optimize image for web delivery.
        
        Args:
            image_path: Path to original image
            
        Returns:
            Tuple of (optimized_image_bytes, content_type)
        """
        with Image.open(image_path) as img:
            # Convert to RGB if necessary (for JPEG output)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize if too large
            if img.size[0] > self.max_dimensions[0] or img.size[1] > self.max_dimensions[1]:
                img.thumbnail(self.max_dimensions, Image.Resampling.LANCZOS)
            
            # Save optimized image
            from io import BytesIO
            output = BytesIO()
            img.save(output, format='JPEG', quality=85, optimize=True)
            
            return output.getvalue(), 'image/jpeg'
    
    async def _validate_image(self, image_path: Path) -> Dict[str, Any]:
        """
        Validate an image file.
        
        Args:
            image_path: Path to image file
            
        Returns:
            Validation result
        """
        result = {'valid': False, 'error': None}
        
        try:
            # Check file size
            file_size = image_path.stat().st_size
            if file_size > self.max_file_size:
                result['error'] = f"File too large: {file_size} bytes"
                return result
            
            # Check if it's a valid image
            with Image.open(image_path) as img:
                # Verify image can be loaded
                img.verify()
                
                # Re-open for dimension check (verify() closes the image)
                with Image.open(image_path) as img2:
                    width, height = img2.size
                    
                    # Check dimensions
                    if width < 100 or height < 100:
                        result['error'] = f"Image too small: {width}x{height} (minimum: 100x100)"
                        return result
                    
                    if width > 4000 or height > 4000:
                        result['error'] = f"Image too large: {width}x{height} (maximum: 4000x4000)"
                        return result
            
            result['valid'] = True
            
        except Exception as e:
            result['error'] = f"Invalid image: {str(e)}"
        
        return result
    
    def _filename_to_character_name(self, filename: str) -> str:
        """
        Convert filename to character name.
        
        Args:
            filename: Filename without extension
            
        Returns:
            Character name with proper formatting
        """
        # Replace hyphens and underscores with spaces
        name = filename.replace('-', ' ').replace('_', ' ')
        
        # Title case each word
        name = ' '.join(word.capitalize() for word in name.split())
        
        return name
    
    def _character_name_to_filename(self, character_name: str) -> str:
        """
        Convert character name to safe filename.
        
        Args:
            character_name: Character name
            
        Returns:
            Safe filename (without extension)
        """
        # Convert to lowercase and replace spaces with hyphens
        filename = character_name.lower().replace(' ', '-')
        
        # Remove special characters
        safe_chars = 'abcdefghijklmnopqrstuvwxyz0123456789-'
        filename = ''.join(c for c in filename if c in safe_chars)
        
        # Remove multiple consecutive hyphens
        while '--' in filename:
            filename = filename.replace('--', '-')
        
        # Remove leading/trailing hyphens
        filename = filename.strip('-')
        
        return filename

async def main():
    """CLI entry point"""
    parser = argparse.ArgumentParser(description='ComicGuess Image Management CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Upload single image command
    upload_parser = subparsers.add_parser('upload', help='Upload a single image')
    upload_parser.add_argument('universe', choices=['marvel', 'DC', 'image'], help='Comic universe')
    upload_parser.add_argument('character', help='Character name')
    upload_parser.add_argument('image', type=Path, help='Image file path')
    upload_parser.add_argument('--no-optimize', action='store_true', help='Skip image optimization')
    upload_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing image')
    
    # Bulk upload command
    bulk_parser = subparsers.add_parser('bulk-upload', help='Upload multiple images from directory')
    bulk_parser.add_argument('universe', choices=['marvel', 'DC', 'image'], help='Comic universe')
    bulk_parser.add_argument('directory', type=Path, help='Directory containing images')
    bulk_parser.add_argument('--no-optimize', action='store_true', help='Skip image optimization')
    bulk_parser.add_argument('--overwrite', action='store_true', help='Overwrite existing images')
    bulk_parser.add_argument('--dry-run', action='store_true', help='Validate only, do not upload')
    
    # List images command
    list_parser = subparsers.add_parser('list', help='List images in universe')
    list_parser.add_argument('universe', choices=['marvel', 'DC', 'image'], help='Comic universe')
    
    # Validate images command
    validate_parser = subparsers.add_parser('validate', help='Validate images in storage')
    validate_parser.add_argument('--universe', choices=['marvel', 'DC', 'image'], help='Validate specific universe')
    
    # Delete image command
    delete_parser = subparsers.add_parser('delete', help='Delete a character image')
    delete_parser.add_argument('universe', choices=['marvel', 'DC', 'image'], help='Comic universe')
    delete_parser.add_argument('character', help='Character name')
    delete_parser.add_argument('--confirm', action='store_true', help='Confirm deletion')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = ImageManager()
    
    try:
        if args.command == 'upload':
            result = await manager.upload_image(
                args.universe, args.character, args.image,
                optimize=not args.no_optimize, overwrite=args.overwrite
            )
            
            if result['success']:
                print(f"Successfully uploaded {args.character}")
                print(f"  Original size: {result['original_size']} bytes")
                print(f"  Final size: {result['final_size']} bytes")
                print(f"  Blob path: {result['blob_path']}")
            else:
                print(f"Upload failed: {result['error']}")
                sys.exit(1)
        
        elif args.command == 'bulk-upload':
            stats = await manager.bulk_upload(
                args.universe, args.directory,
                optimize=not args.no_optimize, overwrite=args.overwrite,
                dry_run=args.dry_run
            )
            
            print(f"Bulk Upload Results:")
            print(f"  Total files: {stats['total_files']}")
            print(f"  Valid images: {stats['valid_images']}")
            print(f"  Invalid images: {stats['invalid_images']}")
            print(f"  Uploaded: {stats['uploaded']}")
            print(f"  Skipped: {stats['skipped']}")
            print(f"  Original size: {stats['total_original_size']} bytes")
            print(f"  Final size: {stats['total_final_size']} bytes")
            
            if stats['errors']:
                print(f"\nErrors:")
                for error in stats['errors'][:10]:
                    print(f"  {error}")
                if len(stats['errors']) > 10:
                    print(f"  ... and {len(stats['errors']) - 10} more errors")
        
        elif args.command == 'list':
            characters = await manager.list_images(args.universe)
            print(f"Images in {args.universe} universe ({len(characters)} total):")
            for character in sorted(characters):
                print(f"  {character}")
        
        elif args.command == 'validate':
            results = await manager.validate_images(args.universe)
            print(f"Image Validation Results:")
            print(f"  Total images: {results['total_images']}")
            print(f"  Accessible: {results['accessible_images']}")
            print(f"  Inaccessible: {results['inaccessible_images']}")
            
            if results['errors']:
                print(f"\nErrors:")
                for error in results['errors']:
                    print(f"  {error}")
        
        elif args.command == 'delete':
            success = await manager.delete_image(args.universe, args.character, args.confirm)
            if args.confirm:
                if success:
                    print(f"Deleted image for {args.character}")
                else:
                    print(f"Failed to delete image for {args.character}")
                    sys.exit(1)
            else:
                print("Use --confirm to actually delete the image")
    
    except Exception as e:
        logger.error(f"Command failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())