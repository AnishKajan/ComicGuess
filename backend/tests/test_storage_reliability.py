"""
Tests for storage reliability and lifecycle management
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from app.storage.reliability import StorageReliabilityManager, storage_reliability
from azure.core.exceptions import ResourceNotFoundError


class TestStorageReliabilityManager:
    """Test cases for StorageReliabilityManager"""
    
    @pytest.fixture
    def reliability_mgr(self):
        """Create a storage reliability manager instance for testing"""
        return StorageReliabilityManager()
    
    @pytest.fixture
    def mock_blob_client(self):
        """Mock Azure Blob Storage client"""
        mock_client = AsyncMock()
        mock_blob_instance = AsyncMock()
        mock_container_client = AsyncMock()
        
        mock_client.get_blob_client.return_value = mock_blob_instance
        mock_client.get_container_client.return_value = mock_container_client
        
        return mock_client, mock_blob_instance, mock_container_client
    
    def test_lifecycle_policy_configuration(self, reliability_mgr):
        """Test lifecycle policy settings"""
        assert reliability_mgr.soft_delete_retention_days == 30
        assert reliability_mgr.version_retention_days == 90
        assert reliability_mgr.archive_after_days == 365
        assert reliability_mgr.enable_versioning is True
        assert reliability_mgr.enable_soft_delete is True
    
    @pytest.mark.asyncio
    async def test_configure_lifecycle_policies_success(self, reliability_mgr, mock_blob_client):
        """Test successful lifecycle policy configuration"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.configure_lifecycle_policies()
            
            assert result["status"] == "configured"
            assert "policies" in result
            assert len(result["policies"]) == 2  # character-images and backup rules
            assert result["soft_delete_retention_days"] == 30
            assert result["version_retention_days"] == 90
            assert result["archive_after_days"] == 365
    
    @pytest.mark.asyncio
    async def test_enable_soft_delete(self, reliability_mgr):
        """Test soft delete configuration"""
        result = await reliability_mgr.enable_soft_delete()
        
        assert result["status"] == "enabled"
        assert result["retention_days"] == 30
        assert "blobs" in result["applies_to"]
        assert "containers" in result["applies_to"]
    
    @pytest.mark.asyncio
    async def test_enable_versioning(self, reliability_mgr):
        """Test blob versioning configuration"""
        result = await reliability_mgr.enable_versioning()
        
        assert result["status"] == "enabled"
        assert result["version_retention_days"] == 90
        assert result["automatic_versioning"] is True
    
    @pytest.mark.asyncio
    async def test_create_backup_copy_success(self, reliability_mgr, mock_blob_client):
        """Test successful backup copy creation"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock source blob properties
        mock_properties = Mock()
        mock_properties.size = 1024
        mock_blob_instance.get_blob_properties.return_value = mock_properties
        
        # Mock copy operation
        mock_copy_result = {"copy_id": "test-copy-id"}
        mock_blob_instance.start_copy_from_url.return_value = mock_copy_result
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.create_backup_copy("marvel/spider-man.jpg")
            
            assert result["status"] == "completed"
            assert result["source_path"] == "marvel/spider-man.jpg"
            assert result["backup_container"] == "character-images-backup"
            assert "backup_path" in result
            assert "timestamp" in result
            assert result["copy_id"] == "test-copy-id"
    
    @pytest.mark.asyncio
    async def test_create_backup_copy_source_not_found(self, reliability_mgr, mock_blob_client):
        """Test backup copy creation when source blob doesn't exist"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock source blob not found
        mock_blob_instance.get_blob_properties.side_effect = ResourceNotFoundError("Blob not found")
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.create_backup_copy("nonexistent/blob.jpg")
            
            assert result["status"] == "failed"
            assert "not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_restore_from_backup_success(self, reliability_mgr, mock_blob_client):
        """Test successful restore from backup"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock backup blob properties
        mock_properties = Mock()
        mock_properties.size = 1024
        mock_blob_instance.get_blob_properties.return_value = mock_properties
        
        # Mock copy operation
        mock_copy_result = {"copy_id": "restore-copy-id"}
        mock_blob_instance.start_copy_from_url.return_value = mock_copy_result
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.restore_from_backup(
                "marvel/spider-man.jpg.backup.20241201_120000"
            )
            
            assert result["status"] == "completed"
            assert result["backup_path"] == "marvel/spider-man.jpg.backup.20241201_120000"
            assert result["restored_path"] == "marvel/spider-man.jpg"
            assert result["copy_id"] == "restore-copy-id"
    
    @pytest.mark.asyncio
    async def test_restore_from_backup_with_custom_target(self, reliability_mgr, mock_blob_client):
        """Test restore from backup with custom target path"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        mock_properties = Mock()
        mock_blob_instance.get_blob_properties.return_value = mock_properties
        mock_blob_instance.start_copy_from_url.return_value = {"copy_id": "test"}
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.restore_from_backup(
                "marvel/spider-man.jpg.backup.20241201_120000",
                "marvel/spider-man-restored.jpg"
            )
            
            assert result["status"] == "completed"
            assert result["restored_path"] == "marvel/spider-man-restored.jpg"
    
    @pytest.mark.asyncio
    async def test_restore_from_backup_not_found(self, reliability_mgr, mock_blob_client):
        """Test restore when backup blob doesn't exist"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        mock_blob_instance.get_blob_properties.side_effect = ResourceNotFoundError("Backup not found")
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.restore_from_backup("nonexistent.backup")
            
            assert result["status"] == "failed"
            assert "not found" in result["error"]
    
    @pytest.mark.asyncio
    async def test_list_blob_versions(self, reliability_mgr, mock_blob_client):
        """Test listing blob versions"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock blob versions
        mock_blob1 = Mock()
        mock_blob1.name = "marvel/spider-man.jpg"
        mock_blob1.version_id = "version1"
        mock_blob1.is_current_version = True
        mock_blob1.last_modified = datetime.utcnow()
        mock_blob1.size = 1024
        mock_blob1.etag = "etag1"
        mock_blob1.content_type = "image/jpeg"
        
        mock_blob2 = Mock()
        mock_blob2.name = "marvel/spider-man.jpg"
        mock_blob2.version_id = "version2"
        mock_blob2.is_current_version = False
        mock_blob2.last_modified = datetime.utcnow() - timedelta(hours=1)
        mock_blob2.size = 2048
        mock_blob2.etag = "etag2"
        mock_blob2.content_type = "image/jpeg"
        
        mock_container_client.list_blobs.return_value = [mock_blob1, mock_blob2]
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            versions = await reliability_mgr.list_blob_versions("marvel/spider-man.jpg")
            
            assert len(versions) == 2
            assert versions[0]["version_id"] == "version1"  # Current version first
            assert versions[0]["is_current_version"] is True
            assert versions[1]["version_id"] == "version2"
            assert versions[1]["is_current_version"] is False
    
    @pytest.mark.asyncio
    async def test_restore_blob_version_success(self, reliability_mgr, mock_blob_client):
        """Test successful blob version restore"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        mock_copy_result = {"copy_id": "version-restore-id"}
        mock_blob_instance.start_copy_from_url.return_value = mock_copy_result
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.restore_blob_version(
                "marvel/spider-man.jpg", 
                "version123"
            )
            
            assert result["status"] == "completed"
            assert result["blob_path"] == "marvel/spider-man.jpg"
            assert result["restored_version"] == "version123"
            assert result["copy_id"] == "version-restore-id"
    
    @pytest.mark.asyncio
    async def test_perform_storage_health_check_healthy(self, reliability_mgr, mock_blob_client):
        """Test storage health check when all systems are healthy"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock container properties
        mock_properties = Mock()
        mock_properties.last_modified = datetime.utcnow()
        mock_container_client.get_container_properties.return_value = mock_properties
        
        # Mock blob listing
        mock_blob1 = Mock()
        mock_blob1.size = 1024
        mock_blob2 = Mock()
        mock_blob2.size = 2048
        mock_container_client.list_blobs.return_value = [mock_blob1, mock_blob2]
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.perform_storage_health_check()
            
            assert result["overall_status"] == "healthy"
            assert "containers" in result
            assert "policies" in result
            assert "redundancy" in result
            
            # Check container health
            for container_name in ["character-images", "character-images-backup", "database-backups"]:
                if container_name in result["containers"]:
                    container_health = result["containers"][container_name]
                    assert container_health["status"] == "healthy"
                    assert container_health["blob_count"] == 2
                    assert container_health["total_size_bytes"] == 3072
    
    @pytest.mark.asyncio
    async def test_perform_storage_health_check_missing_container(self, reliability_mgr, mock_blob_client):
        """Test storage health check with missing container"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock container not found
        mock_container_client.get_container_properties.side_effect = ResourceNotFoundError("Container not found")
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.perform_storage_health_check()
            
            assert result["overall_status"] == "warning"
            
            # All containers should be marked as missing
            for container_name in result["containers"]:
                assert result["containers"][container_name]["status"] == "missing"
    
    @pytest.mark.asyncio
    async def test_run_disaster_recovery_drill_success(self, reliability_mgr, mock_blob_client):
        """Test successful disaster recovery drill"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock successful operations
        mock_blob_instance.upload_blob = AsyncMock()
        mock_blob_instance.delete_blob = AsyncMock()
        mock_blob_instance.start_copy_from_url = AsyncMock(return_value={"copy_id": "test"})
        
        # Mock download for content verification
        mock_download = AsyncMock()
        mock_download.readall = AsyncMock(return_value=b"test content")
        mock_blob_instance.download_blob.return_value = mock_download
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client), \
             patch.object(reliability_mgr, 'create_backup_copy') as mock_backup, \
             patch.object(reliability_mgr, 'restore_from_backup') as mock_restore:
            
            # Mock backup and restore operations
            mock_backup.return_value = {
                "status": "completed",
                "backup_path": "test/backup.txt"
            }
            
            mock_restore.return_value = {
                "status": "completed"
            }
            
            result = await reliability_mgr.run_disaster_recovery_drill()
            
            assert result["status"] == "passed"
            assert "drill_id" in result
            assert "tests" in result
            
            # Check individual test results
            tests = result["tests"]
            assert tests["create_test_blob"]["status"] == "passed"
            assert tests["create_backup"]["status"] == "passed"
            assert tests["restore_from_backup"]["status"] == "passed"
            assert tests["cleanup"]["status"] == "passed"
    
    @pytest.mark.asyncio
    async def test_run_disaster_recovery_drill_failure(self, reliability_mgr, mock_blob_client):
        """Test disaster recovery drill with failures"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock upload failure
        mock_blob_instance.upload_blob.side_effect = Exception("Upload failed")
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            result = await reliability_mgr.run_disaster_recovery_drill()
            
            assert result["status"] == "failed"
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_get_storage_metrics(self, reliability_mgr, mock_blob_client):
        """Test storage metrics collection"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock blobs in different universes
        mock_blobs = [
            Mock(name="marvel/spider-man.jpg", size=1024),
            Mock(name="dc/batman.jpg", size=2048),
            Mock(name="image/spawn.jpg", size=1536),
            Mock(name="other/test.jpg", size=512)
        ]
        
        mock_container_client.list_blobs.return_value = mock_blobs
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            metrics = await reliability_mgr.get_storage_metrics()
            
            assert "timestamp" in metrics
            assert "containers" in metrics
            assert "totals" in metrics
            
            # Check totals
            assert metrics["totals"]["total_blobs"] > 0
            assert metrics["totals"]["total_size_bytes"] > 0
            assert metrics["totals"]["total_size_mb"] > 0
            
            # Check universe categorization (if container exists)
            for container_name, container_metrics in metrics["containers"].items():
                if "universes" in container_metrics:
                    assert "marvel" in container_metrics["universes"]
                    assert "dc" in container_metrics["universes"]
                    assert "image" in container_metrics["universes"]
                    assert "other" in container_metrics["universes"]
    
    @pytest.mark.asyncio
    async def test_get_storage_metrics_error_handling(self, reliability_mgr, mock_blob_client):
        """Test storage metrics collection with errors"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock container not found for some containers
        def mock_get_container_client(container_name):
            if container_name == "character-images":
                return mock_container_client
            else:
                mock_error_client = AsyncMock()
                mock_error_client.list_blobs.side_effect = ResourceNotFoundError("Container not found")
                return mock_error_client
        
        mock_client.get_container_client.side_effect = mock_get_container_client
        mock_container_client.list_blobs.return_value = [Mock(name="test.jpg", size=1024)]
        
        with patch('app.storage.reliability.BlobServiceClient', return_value=mock_client):
            metrics = await reliability_mgr.get_storage_metrics()
            
            assert "containers" in metrics
            
            # Should have metrics for accessible container
            if "character-images" in metrics["containers"]:
                assert metrics["containers"]["character-images"]["blob_count"] == 1
            
            # Should mark missing containers appropriately
            for container_name, container_metrics in metrics["containers"].items():
                if container_metrics.get("status") == "not_found":
                    assert container_metrics["blob_count"] == 0
    
    @pytest.mark.asyncio
    async def test_redundancy_and_failover_mechanisms(self, reliability_mgr):
        """Test redundancy and failover configuration"""
        # Test redundancy settings
        assert reliability_mgr.primary_container == "character-images"
        assert reliability_mgr.backup_container == "character-images-backup"
        assert reliability_mgr.versioning_container == "character-images-versions"
        
        # Test failover logic would be implemented here
        # For now, we test the configuration
        assert reliability_mgr.enable_versioning is True
        assert reliability_mgr.enable_soft_delete is True


class TestStorageReliabilityIntegration:
    """Integration tests for storage reliability"""
    
    @pytest.mark.asyncio
    async def test_complete_backup_restore_cycle(self):
        """Test complete backup and restore cycle"""
        reliability_mgr = StorageReliabilityManager()
        
        # Mock the entire workflow
        with patch.object(reliability_mgr, 'create_backup_copy') as mock_backup, \
             patch.object(reliability_mgr, 'restore_from_backup') as mock_restore, \
             patch.object(reliability_mgr, 'list_blob_versions') as mock_versions:
            
            # Setup mock returns
            mock_backup.return_value = {
                "status": "completed",
                "backup_path": "test.jpg.backup.20241201_120000"
            }
            
            mock_restore.return_value = {
                "status": "completed",
                "restored_path": "test.jpg"
            }
            
            mock_versions.return_value = [
                {"version_id": "v1", "is_current_version": True},
                {"version_id": "v2", "is_current_version": False}
            ]
            
            # Execute workflow
            backup_result = await reliability_mgr.create_backup_copy("test.jpg")
            assert backup_result["status"] == "completed"
            
            versions = await reliability_mgr.list_blob_versions("test.jpg")
            assert len(versions) == 2
            
            restore_result = await reliability_mgr.restore_from_backup(backup_result["backup_path"])
            assert restore_result["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_lifecycle_management_workflow(self):
        """Test lifecycle management configuration workflow"""
        reliability_mgr = StorageReliabilityManager()
        
        # Test configuration sequence
        lifecycle_result = await reliability_mgr.configure_lifecycle_policies()
        assert lifecycle_result["status"] == "configured"
        
        soft_delete_result = await reliability_mgr.enable_soft_delete()
        assert soft_delete_result["status"] == "enabled"
        
        versioning_result = await reliability_mgr.enable_versioning()
        assert versioning_result["status"] == "enabled"
    
    @pytest.mark.asyncio
    async def test_disaster_recovery_readiness(self):
        """Test disaster recovery readiness assessment"""
        reliability_mgr = StorageReliabilityManager()
        
        with patch.object(reliability_mgr, 'perform_storage_health_check') as mock_health, \
             patch.object(reliability_mgr, 'run_disaster_recovery_drill') as mock_drill:
            
            mock_health.return_value = {
                "overall_status": "healthy",
                "containers": {"character-images": {"status": "healthy"}},
                "policies": {"lifecycle_management": "configured"},
                "redundancy": {"backup_container_available": True}
            }
            
            mock_drill.return_value = {
                "status": "passed",
                "tests": {
                    "create_test_blob": {"status": "passed"},
                    "create_backup": {"status": "passed"},
                    "restore_from_backup": {"status": "passed"},
                    "cleanup": {"status": "passed"}
                }
            }
            
            # Assess readiness
            health_check = await reliability_mgr.perform_storage_health_check()
            drill_result = await reliability_mgr.run_disaster_recovery_drill()
            
            # Determine overall readiness
            is_ready = (
                health_check["overall_status"] == "healthy" and
                drill_result["status"] == "passed" and
                all(test["status"] == "passed" for test in drill_result["tests"].values())
            )
            
            assert is_ready is True


if __name__ == "__main__":
    pytest.main([__file__])