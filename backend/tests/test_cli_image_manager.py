"""
Tests for CLI image management tools.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import Image
import io

from cli.image_manager import ImageManager


class TestImageManager:
    """Test cases for ImageManager CLI tool"""
    
    @pytest.fixture
    def image_manager(self):
        """Create ImageManager instance with mocked blob service"""
        manager = ImageManager()
        manager.blob_service = AsyncMock()
        return manager
    
    @pytest.fixture
    def sample_image_data(self):
        """Create sample image data for testing"""
        # Create a simple test image
        img = Image.new('RGB', (200, 200), color='red')
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        return img_bytes.getvalue()
    
    @pytest.fixture
    def sample_image_file(self, sample_image_data):
        """Create temporary image file for testing"""
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(sample_image_data)
            return Path(f.name)
    
    @pytest.mark.asyncio
    async def test_upload_image_success(self, image_manager, sample_image_file):
        """Test successful image upload"""
        # Mock blob service methods
        image_manager.blob_service.get_image_url.return_value = None  # No existing image
        image_manager.blob_service.upload_image.return_value = 'marvel/spider-man.jpg'
        
        # Upload image
        result = await image_manager.upload_image(
            'marvel', 'Spider-Man', sample_image_file, optimize=True, overwrite=False
        )
        
        # Verify result
        assert result['success'] is True
        assert result['character'] == 'Spider-Man'
        assert result['universe'] == 'marvel'
        assert result['blob_path'] == 'marvel/spider-man.jpg'
        assert result['original_size'] > 0
        assert result['final_size'] > 0
        assert result['error'] is None
        
        # Verify blob service was called
        image_manager.blob_service.upload_image.assert_called_once()
        
        # Clean up
        sample_image_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_image_file_not_found(self, image_manager):
        """Test upload with non-existent file"""
        non_existent_file = Path('/non/existent/file.jpg')
        
        result = await image_manager.upload_image(
            'marvel', 'Spider-Man', non_existent_file
        )
        
        assert result['success'] is False
        assert 'File not found' in result['error']
    
    @pytest.mark.asyncio
    async def test_upload_image_unsupported_format(self, image_manager):
        """Test upload with unsupported file format"""
        # Create temporary file with unsupported extension
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
            f.write(b'not an image')
            txt_file = Path(f.name)
        
        try:
            result = await image_manager.upload_image(
                'marvel', 'Spider-Man', txt_file
            )
            
            assert result['success'] is False
            assert 'Unsupported format' in result['error']
        finally:
            txt_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_image_file_too_large(self, image_manager):
        """Test upload with file that's too large"""
        # Create a large temporary file
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            # Write more than max file size
            large_data = b'x' * (image_manager.max_file_size + 1)
            f.write(large_data)
            large_file = Path(f.name)
        
        try:
            result = await image_manager.upload_image(
                'marvel', 'Spider-Man', large_file
            )
            
            assert result['success'] is False
            assert 'File too large' in result['error']
        finally:
            large_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_image_already_exists_no_overwrite(self, image_manager, sample_image_file):
        """Test upload when image already exists and overwrite is False"""
        # Mock existing image
        image_manager.blob_service.get_image_url.return_value = 'https://example.com/existing.jpg'
        
        result = await image_manager.upload_image(
            'marvel', 'Spider-Man', sample_image_file, overwrite=False
        )
        
        assert result['success'] is False
        assert 'already exists' in result['error']
        
        # Clean up
        sample_image_file.unlink()
    
    @pytest.mark.asyncio
    async def test_upload_image_with_overwrite(self, image_manager, sample_image_file):
        """Test upload with overwrite enabled"""
        # Mock existing image
        image_manager.blob_service.get_image_url.return_value = 'https://example.com/existing.jpg'
        image_manager.blob_service.upload_image.return_value = 'marvel/spider-man.jpg'
        
        result = await image_manager.upload_image(
            'marvel', 'Spider-Man', sample_image_file, overwrite=True
        )
        
        assert result['success'] is True
        
        # Clean up
        sample_image_file.unlink()
    
    @pytest.mark.asyncio
    async def test_bulk_upload_success(self, image_manager, sample_image_data):
        """Test successful bulk upload"""
        # Create temporary directory with images
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test images
            image_files = ['spider-man.jpg', 'iron-man.jpg', 'captain-america.jpg']
            for filename in image_files:
                image_path = temp_path / filename
                with open(image_path, 'wb') as f:
                    f.write(sample_image_data)
            
            # Mock blob service
            image_manager.blob_service.get_image_url.return_value = None  # No existing images
            image_manager.blob_service.upload_image.return_value = 'marvel/test.jpg'
            
            # Perform bulk upload
            stats = await image_manager.bulk_upload(
                'marvel', temp_path, optimize=True, overwrite=False, dry_run=False
            )
            
            # Verify results
            assert stats['total_files'] == 3
            assert stats['valid_images'] == 3
            assert stats['invalid_images'] == 0
            assert stats['uploaded'] == 3
            assert stats['skipped'] == 0
    
    @pytest.mark.asyncio
    async def test_bulk_upload_dry_run(self, image_manager, sample_image_data):
        """Test bulk upload in dry run mode"""
        # Create temporary directory with images
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create test image
            image_path = temp_path / 'spider-man.jpg'
            with open(image_path, 'wb') as f:
                f.write(sample_image_data)
            
            # Perform dry run
            stats = await image_manager.bulk_upload(
                'marvel', temp_path, dry_run=True
            )
            
            # Verify no actual uploads occurred
            assert stats['uploaded'] == 0
            assert stats['valid_images'] == 1
            image_manager.blob_service.upload_image.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_bulk_upload_no_images(self, image_manager):
        """Test bulk upload with directory containing no images"""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create non-image file
            text_file = temp_path / 'readme.txt'
            text_file.write_text('This is not an image')
            
            stats = await image_manager.bulk_upload('marvel', temp_path)
            
            assert stats['total_files'] == 0
            assert stats['valid_images'] == 0
    
    @pytest.mark.asyncio
    async def test_validate_images(self, image_manager):
        """Test image validation"""
        # Mock blob service responses
        image_manager.blob_service.list_images_by_universe.return_value = [
            'Spider-Man', 'Iron Man', 'Captain America'
        ]
        image_manager.blob_service.get_image_url.side_effect = [
            'https://example.com/spider-man.jpg',  # Accessible
            'https://example.com/iron-man.jpg',    # Accessible
            None  # Inaccessible
        ]
        
        results = await image_manager.validate_images('marvel')
        
        assert results['total_images'] == 3
        assert results['accessible_images'] == 2
        assert results['inaccessible_images'] == 1
        assert len(results['errors']) == 1
    
    @pytest.mark.asyncio
    async def test_list_images(self, image_manager):
        """Test listing images"""
        expected_characters = ['Spider-Man', 'Iron Man', 'Captain America']
        image_manager.blob_service.list_images_by_universe.return_value = expected_characters
        
        characters = await image_manager.list_images('marvel')
        
        assert characters == expected_characters
        image_manager.blob_service.list_images_by_universe.assert_called_once_with('marvel')
    
    @pytest.mark.asyncio
    async def test_delete_image_without_confirm(self, image_manager):
        """Test delete image without confirmation"""
        success = await image_manager.delete_image('marvel', 'Spider-Man', confirm=False)
        
        assert success is False
        image_manager.blob_service.delete_image.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_delete_image_with_confirm(self, image_manager):
        """Test delete image with confirmation"""
        image_manager.blob_service.delete_image.return_value = True
        
        success = await image_manager.delete_image('marvel', 'Spider-Man', confirm=True)
        
        assert success is True
        image_manager.blob_service.delete_image.assert_called_once_with('marvel', 'Spider-Man')
    
    @pytest.mark.asyncio
    async def test_optimize_image(self, image_manager, sample_image_file):
        """Test image optimization"""
        optimized_data, content_type = await image_manager._optimize_image(sample_image_file)
        
        assert isinstance(optimized_data, bytes)
        assert content_type == 'image/jpeg'
        assert len(optimized_data) > 0
        
        # Clean up
        sample_image_file.unlink()
    
    @pytest.mark.asyncio
    async def test_optimize_image_with_transparency(self, image_manager):
        """Test image optimization with transparent PNG"""
        # Create PNG with transparency
        img = Image.new('RGBA', (200, 200), (255, 0, 0, 128))  # Semi-transparent red
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            img.save(f, format='PNG')
            png_path = Path(f.name)
        
        try:
            optimized_data, content_type = await image_manager._optimize_image(png_path)
            
            assert isinstance(optimized_data, bytes)
            assert content_type == 'image/jpeg'  # Should be converted to JPEG
            assert len(optimized_data) > 0
        finally:
            png_path.unlink()
    
    @pytest.mark.asyncio
    async def test_optimize_image_large_dimensions(self, image_manager):
        """Test image optimization with large dimensions"""
        # Create large image
        large_img = Image.new('RGB', (3000, 3000), color='blue')
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            large_img.save(f, format='JPEG')
            large_path = Path(f.name)
        
        try:
            optimized_data, content_type = await image_manager._optimize_image(large_path)
            
            # Verify image was resized
            optimized_img = Image.open(io.BytesIO(optimized_data))
            assert optimized_img.size[0] <= image_manager.max_dimensions[0]
            assert optimized_img.size[1] <= image_manager.max_dimensions[1]
        finally:
            large_path.unlink()
    
    @pytest.mark.asyncio
    async def test_validate_image_success(self, image_manager, sample_image_file):
        """Test successful image validation"""
        result = await image_manager._validate_image(sample_image_file)
        
        assert result['valid'] is True
        assert result['error'] is None
        
        # Clean up
        sample_image_file.unlink()
    
    @pytest.mark.asyncio
    async def test_validate_image_too_small(self, image_manager):
        """Test image validation with image too small"""
        # Create very small image
        small_img = Image.new('RGB', (50, 50), color='red')
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            small_img.save(f, format='JPEG')
            small_path = Path(f.name)
        
        try:
            result = await image_manager._validate_image(small_path)
            
            assert result['valid'] is False
            assert 'too small' in result['error']
        finally:
            small_path.unlink()
    
    @pytest.mark.asyncio
    async def test_validate_image_too_large_dimensions(self, image_manager):
        """Test image validation with dimensions too large"""
        # Create image with very large dimensions
        large_img = Image.new('RGB', (5000, 5000), color='red')
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            large_img.save(f, format='JPEG', quality=1)  # Low quality to keep file size manageable
            large_path = Path(f.name)
        
        try:
            result = await image_manager._validate_image(large_path)
            
            assert result['valid'] is False
            assert 'too large' in result['error']
        finally:
            large_path.unlink()
    
    @pytest.mark.asyncio
    async def test_validate_image_invalid_file(self, image_manager):
        """Test image validation with invalid image file"""
        # Create file that's not an image
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as f:
            f.write(b'This is not an image file')
            invalid_path = Path(f.name)
        
        try:
            result = await image_manager._validate_image(invalid_path)
            
            assert result['valid'] is False
            assert 'Invalid image' in result['error']
        finally:
            invalid_path.unlink()
    
    def test_filename_to_character_name(self, image_manager):
        """Test filename to character name conversion"""
        assert image_manager._filename_to_character_name('spider-man') == 'Spider Man'
        assert image_manager._filename_to_character_name('iron_man') == 'Iron Man'
        assert image_manager._filename_to_character_name('captain-america') == 'Captain America'
        assert image_manager._filename_to_character_name('dr-doom') == 'Dr Doom'
    
    def test_character_name_to_filename(self, image_manager):
        """Test character name to filename conversion"""
        assert image_manager._character_name_to_filename('Spider-Man') == 'spider-man'
        assert image_manager._character_name_to_filename('Iron Man') == 'iron-man'
        assert image_manager._character_name_to_filename('Captain America') == 'captain-america'
        assert image_manager._character_name_to_filename('Dr. Doom') == 'dr-doom'
        assert image_manager._character_name_to_filename('X-23') == 'x-23'
    
    @pytest.mark.asyncio
    async def test_bulk_upload_invalid_directory(self, image_manager):
        """Test bulk upload with invalid directory"""
        non_existent_dir = Path('/non/existent/directory')
        
        with pytest.raises(ValueError, match="Directory not found"):
            await image_manager.bulk_upload('marvel', non_existent_dir)