"""
Tests for image optimization and processing functionality.
"""

import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys

# Add scripts directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../scripts'))

try:
    from image_optimizer import ImageOptimizer, ImageOptimizationResult, AzureBlobImageOptimizer
    from image_processing_workflow import ImageProcessingWorkflow, ImageProcessingJob, CloudflareCache
    PIL_AVAILABLE = True
except ImportError:
    # Mock classes if PIL or other dependencies are not available
    ImageOptimizer = None
    ImageOptimizationResult = None
    AzureBlobImageOptimizer = None
    ImageProcessingWorkflow = None
    ImageProcessingJob = None
    CloudflareCache = None
    PIL_AVAILABLE = False

class TestImageOptimizer:
    """Test image optimization functionality."""
    
    @pytest.fixture
    def mock_optimizer(self):
        """Create a mock image optimizer."""
        if ImageOptimizer is None:
            pytest.skip("PIL and image processing dependencies not available")
        
        return ImageOptimizer(
            target_width=800,
            target_height=600,
            quality=85,
            output_format='WEBP'
        )
    
    def test_optimizer_initialization(self, mock_optimizer):
        """Test image optimizer initialization."""
        if ImageOptimizer is None:
            pytest.skip("PIL and image processing dependencies not available")
        
        assert mock_optimizer.target_width == 800
        assert mock_optimizer.target_height == 600
        assert mock_optimizer.quality == 85
        assert mock_optimizer.output_format == 'WEBP'
        assert 'JPEG' in mock_optimizer.supported_formats
        assert 'PNG' in mock_optimizer.supported_formats
        assert 'WEBP' in mock_optimizer.supported_formats
    
    @patch('image_optimizer.Image')
    def test_exif_stripping(self, mock_image, mock_optimizer):
        """Test EXIF data stripping functionality."""
        if ImageOptimizer is None:
            pytest.skip("PIL and image processing dependencies not available")
        
        # Mock image with EXIF data
        mock_img = Mock()
        mock_img._getexif.return_value = {'some': 'exif_data'}
        mock_img.mode = 'RGB'
        mock_img.convert.return_value = mock_img
        
        cleaned_img, exif_present = mock_optimizer.strip_exif_data(mock_img)
        
        assert exif_present is True
        mock_img.convert.assert_called_with('RGB')
    
    @patch('image_optimizer.Image')
    def test_image_resizing(self, mock_image, mock_optimizer):
        """Test image resizing functionality."""
        if ImageOptimizer is None:
            pytest.skip("PIL and image processing dependencies not available")
        
        # Mock large image that needs resizing
        mock_img = Mock()
        mock_img.size = (1600, 1200)  # Larger than target
        mock_img.resize.return_value = mock_img
        
        resized_img = mock_optimizer.resize_image(mock_img)
        
        # Should call resize since image is larger than target
        mock_img.resize.assert_called_once()
        
        # Test with small image that doesn't need resizing
        mock_small_img = Mock()
        mock_small_img.size = (400, 300)  # Smaller than target
        
        result = mock_optimizer.resize_image(mock_small_img)
        
        # Should return original image without resizing
        assert result == mock_small_img
    
    def test_optimization_result_structure(self):
        """Test ImageOptimizationResult data structure."""
        if ImageOptimizationResult is None:
            pytest.skip("Image optimization dependencies not available")
        
        result = ImageOptimizationResult(
            original_path='/test/input.jpg',
            optimized_path='/test/output.webp',
            original_size_bytes=1000000,
            optimized_size_bytes=500000,
            compression_ratio=50.0,
            format_original='JPEG',
            format_optimized='WEBP',
            dimensions_original=(1920, 1080),
            dimensions_optimized=(800, 450),
            exif_stripped=True,
            processing_time_seconds=2.5
        )
        
        assert result.original_path == '/test/input.jpg'
        assert result.compression_ratio == 50.0
        assert result.exif_stripped is True
        assert result.error is None

class TestAzureBlobImageOptimizer:
    """Test Azure Blob Storage image optimization."""
    
    @pytest.fixture
    def mock_blob_optimizer(self):
        """Create a mock Azure Blob image optimizer."""
        if AzureBlobImageOptimizer is None:
            pytest.skip("Azure SDK dependencies not available")
        
        with patch('image_optimizer.BlobServiceClient'):
            return AzureBlobImageOptimizer('test_connection', 'test_container')
    
    @pytest.mark.asyncio
    async def test_blob_optimization_workflow(self, mock_blob_optimizer):
        """Test blob optimization workflow."""
        if AzureBlobImageOptimizer is None:
            pytest.skip("Azure SDK dependencies not available")
        
        # Mock blob client and download
        mock_blob_client = Mock()
        mock_download_stream = Mock()
        mock_download_stream.chunks.return_value = [b'fake_image_data']
        mock_blob_client.download_blob.return_value = mock_download_stream
        
        mock_blob_optimizer.blob_service_client.get_blob_client.return_value = mock_blob_client
        
        # Mock optimizer
        mock_optimization_result = ImageOptimizationResult(
            original_path='temp_input',
            optimized_path='temp_output.webp',
            original_size_bytes=1000,
            optimized_size_bytes=500,
            compression_ratio=50.0,
            format_original='JPEG',
            format_optimized='WEBP',
            dimensions_original=(800, 600),
            dimensions_optimized=(800, 600),
            exif_stripped=True,
            processing_time_seconds=1.0
        )
        
        mock_blob_optimizer.optimizer.optimize_single_image = Mock(return_value=mock_optimization_result)
        
        # Mock file operations
        with patch('aiofiles.open'), \
             patch('os.path.getsize', return_value=1000), \
             patch('os.makedirs'), \
             patch('pathlib.Path.exists', return_value=True), \
             patch('pathlib.Path.unlink'):
            
            result = await mock_blob_optimizer.optimize_blob_image('test/image.jpg')
            
            assert result.compression_ratio == 50.0
            assert result.error is None

class TestImageProcessingWorkflow:
    """Test image processing workflow."""
    
    @pytest.fixture
    def mock_workflow(self):
        """Create a mock image processing workflow."""
        if ImageProcessingWorkflow is None:
            pytest.skip("Image processing workflow dependencies not available")
        
        with patch('image_processing_workflow.BlobServiceClient'):
            return ImageProcessingWorkflow(
                azure_connection_string='test_connection',
                container_name='test_container',
                cdn_base_url='https://cdn.example.com'
            )
    
    def test_blob_path_generation(self, mock_workflow):
        """Test blob path generation for different formats."""
        if ImageProcessingWorkflow is None:
            pytest.skip("Image processing workflow dependencies not available")
        
        job = ImageProcessingJob(
            source_path='/test/image.jpg',
            universe='marvel',
            character_name='Spider-Man',
            is_primary=True
        )
        
        paths = mock_workflow.generate_blob_paths(job)
        
        assert 'original' in paths
        assert 'webp' in paths
        assert 'avif' in paths
        assert 'thumbnail' in paths
        
        # Check path structure
        assert paths['original'].startswith('marvel/spider-man/')
        assert paths['webp'].endswith('.webp')
        assert paths['avif'].endswith('.avif')
    
    def test_image_processing_job_structure(self):
        """Test ImageProcessingJob data structure."""
        if ImageProcessingJob is None:
            pytest.skip("Image processing workflow dependencies not available")
        
        job = ImageProcessingJob(
            source_path='/test/image.jpg',
            universe='dc',
            character_name='Batman',
            is_primary=True,
            metadata={'artist': 'Test Artist', 'year': '2024'}
        )
        
        assert job.source_path == '/test/image.jpg'
        assert job.universe == 'dc'
        assert job.character_name == 'Batman'
        assert job.is_primary is True
        assert job.metadata['artist'] == 'Test Artist'

class TestCloudflareCache:
    """Test Cloudflare cache management."""
    
    @pytest.fixture
    def mock_cloudflare(self):
        """Create a mock Cloudflare cache manager."""
        if CloudflareCache is None:
            pytest.skip("Cloudflare cache dependencies not available")
        
        return CloudflareCache('test_zone_id', 'test_api_token')
    
    @patch('requests.post')
    def test_cache_purge_by_urls(self, mock_post, mock_cloudflare):
        """Test cache purging by URLs."""
        if CloudflareCache is None:
            pytest.skip("Cloudflare cache dependencies not available")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        urls = ['https://cdn.example.com/image1.webp', 'https://cdn.example.com/image2.webp']
        result = mock_cloudflare.purge_cache_by_urls(urls)
        
        assert result is True
        mock_post.assert_called_once()
        
        # Check request data
        call_args = mock_post.call_args
        assert 'files' in call_args[1]['json']
        assert call_args[1]['json']['files'] == urls
    
    @patch('requests.post')
    def test_cache_purge_by_tags(self, mock_post, mock_cloudflare):
        """Test cache purging by tags."""
        if CloudflareCache is None:
            pytest.skip("Cloudflare cache dependencies not available")
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'success': True}
        mock_post.return_value = mock_response
        
        tags = ['universe:marvel', 'character:spider-man']
        result = mock_cloudflare.purge_cache_by_tags(tags)
        
        assert result is True
        mock_post.assert_called_once()
        
        # Check request data
        call_args = mock_post.call_args
        assert 'tags' in call_args[1]['json']
        assert call_args[1]['json']['tags'] == tags

class TestImageOptimizationFiles:
    """Test that image optimization files exist and are properly structured."""
    
    def test_image_optimizer_file_exists(self):
        """Test that image optimizer script exists."""
        optimizer_file = os.path.join(os.path.dirname(__file__), '../../scripts/image-optimizer.py')
        assert os.path.exists(optimizer_file)
        
        with open(optimizer_file, 'r') as f:
            content = f.read()
        
        # Check for required classes and functions
        assert 'class ImageOptimizer' in content
        assert 'class AzureBlobImageOptimizer' in content
        assert 'def strip_exif_data' in content
        assert 'def resize_image' in content
        assert 'def optimize_single_image' in content
    
    def test_image_processing_workflow_file_exists(self):
        """Test that image processing workflow script exists."""
        workflow_file = os.path.join(os.path.dirname(__file__), '../../scripts/image-processing-workflow.py')
        assert os.path.exists(workflow_file)
        
        with open(workflow_file, 'r') as f:
            content = f.read()
        
        # Check for required classes and functions
        assert 'class ImageProcessingWorkflow' in content
        assert 'class CloudflareCache' in content
        assert 'async def process_image' in content
        assert 'async def batch_process_images' in content

class TestImageOptimizationConfiguration:
    """Test image optimization configuration and parameters."""
    
    def test_optimization_parameters(self):
        """Test optimization parameter validation."""
        # Test different quality settings
        quality_tests = [
            {'quality': 95, 'expected_category': 'high'},
            {'quality': 85, 'expected_category': 'good'},
            {'quality': 70, 'expected_category': 'medium'},
            {'quality': 50, 'expected_category': 'low'}
        ]
        
        for test in quality_tests:
            quality = test['quality']
            
            if quality >= 90:
                category = 'high'
            elif quality >= 80:
                category = 'good'
            elif quality >= 60:
                category = 'medium'
            else:
                category = 'low'
            
            assert category == test['expected_category']
    
    def test_image_format_priorities(self):
        """Test image format priority and support."""
        # Define format priorities (lower number = higher priority)
        format_priorities = {
            'AVIF': 1,    # Next-gen, best compression
            'WEBP': 2,    # Good compression, wide support
            'JPEG': 3,    # Universal support
            'PNG': 4      # Lossless, larger files
        }
        
        # Test format selection logic
        available_formats = ['JPEG', 'WEBP', 'AVIF']
        best_format = min(available_formats, key=lambda f: format_priorities.get(f, 999))
        
        assert best_format == 'AVIF'
        
        # Test fallback when AVIF not available
        available_formats = ['JPEG', 'WEBP']
        best_format = min(available_formats, key=lambda f: format_priorities.get(f, 999))
        
        assert best_format == 'WEBP'
    
    def test_compression_ratio_validation(self):
        """Test compression ratio calculation and validation."""
        test_cases = [
            {'original': 1000000, 'optimized': 500000, 'expected_ratio': 50.0},
            {'original': 2000000, 'optimized': 1600000, 'expected_ratio': 20.0},
            {'original': 500000, 'optimized': 100000, 'expected_ratio': 80.0}
        ]
        
        for case in test_cases:
            original_size = case['original']
            optimized_size = case['optimized']
            
            compression_ratio = ((original_size - optimized_size) / original_size) * 100
            
            assert abs(compression_ratio - case['expected_ratio']) < 0.1

if __name__ == '__main__':
    pytest.main([__file__])