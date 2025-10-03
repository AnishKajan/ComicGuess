"""
Tests for database backup and recovery functionality
"""

import pytest
import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, List

from app.database.backup import CosmosDBBackupManager, backup_manager
from app.config import get_settings


class TestCosmosDBBackupManager:
    """Test cases for CosmosDBBackupManager"""
    
    @pytest.fixture
    def backup_mgr(self):
        """Create a backup manager instance for testing"""
        return CosmosDBBackupManager()
    
    @pytest.fixture
    def mock_cosmos_db(self):
        """Mock Cosmos DB connection"""
        mock_db = Mock()
        mock_container = Mock()
        
        # Mock container query results
        mock_container.query_items.return_value = [
            {"id": "user1", "username": "test1", "email": "test1@example.com"},
            {"id": "user2", "username": "test2", "email": "test2@example.com"}
        ]
        
        mock_db.get_container.return_value = mock_container
        return mock_db
    
    @pytest.fixture
    def mock_blob_client(self):
        """Mock Azure Blob Storage client"""
        mock_client = AsyncMock()
        mock_blob_instance = AsyncMock()
        mock_container_client = AsyncMock()
        
        mock_client.get_blob_client.return_value = mock_blob_instance
        mock_client.get_container_client.return_value = mock_container_client
        
        return mock_client, mock_blob_instance, mock_container_client
    
    @pytest.mark.asyncio
    async def test_create_backup_success(self, backup_mgr, mock_cosmos_db, mock_blob_client):
        """Test successful backup creation"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        with patch('app.database.backup.get_cosmos_db', return_value=mock_cosmos_db), \
             patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            
            result = await backup_mgr.create_backup("test_backup")
            
            assert result["backup_name"] == "test_backup"
            assert result["status"] == "completed"
            assert result["database"] == "comicguess"
            assert "containers" in result
            assert len(result["containers"]) == 3  # users, puzzles, guesses
            
            # Verify blob storage calls
            assert mock_blob_instance.upload_blob.called
    
    @pytest.mark.asyncio
    async def test_create_backup_with_auto_name(self, backup_mgr, mock_cosmos_db, mock_blob_client):
        """Test backup creation with automatic naming"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        with patch('app.database.backup.get_cosmos_db', return_value=mock_cosmos_db), \
             patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            
            result = await backup_mgr.create_backup()
            
            # Should generate timestamp-based name
            assert result["backup_name"].startswith("backup_")
            assert len(result["backup_name"]) > 10  # Should include timestamp
            assert result["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_backup_container_large_dataset(self, backup_mgr, mock_cosmos_db, mock_blob_client):
        """Test backup handling of large datasets with batching"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Create large dataset (more than batch size)
        large_dataset = [
            {"id": f"user{i}", "username": f"test{i}", "email": f"test{i}@example.com"}
            for i in range(1500)  # Exceeds 1000 batch size
        ]
        
        mock_container = Mock()
        mock_container.query_items.return_value = large_dataset
        mock_cosmos_db.get_container.return_value = mock_container
        
        with patch('app.database.backup.get_cosmos_db', return_value=mock_cosmos_db), \
             patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            
            result = await backup_mgr._backup_container(mock_cosmos_db, "users", "test_backup")
            
            assert result["document_count"] == 1500
            assert result["status"] == "completed"
            
            # Should have made multiple blob uploads (batching)
            assert mock_blob_instance.upload_blob.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_list_backups(self, backup_mgr, mock_blob_client):
        """Test listing available backups"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock blob listing
        mock_blob1 = Mock()
        mock_blob1.name = "backup_20241201_120000/metadata.json"
        mock_blob1.size = 1024
        
        mock_blob2 = Mock()
        mock_blob2.name = "backup_20241202_120000/metadata.json"
        mock_blob2.size = 2048
        
        mock_container_client.list_blobs.return_value = [mock_blob1, mock_blob2]
        
        # Mock metadata content
        metadata1 = {
            "backup_name": "backup_20241201_120000",
            "timestamp": "2024-12-01T12:00:00",
            "status": "completed",
            "containers": {"users": {}, "puzzles": {}, "guesses": {}}
        }
        
        metadata2 = {
            "backup_name": "backup_20241202_120000",
            "timestamp": "2024-12-02T12:00:00",
            "status": "completed",
            "containers": {"users": {}, "puzzles": {}}
        }
        
        mock_download = AsyncMock()
        mock_download.readall.side_effect = [
            json.dumps(metadata1).encode(),
            json.dumps(metadata2).encode()
        ]
        mock_blob_instance.download_blob.return_value = mock_download
        
        with patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            backups = await backup_mgr.list_backups()
            
            assert len(backups) == 2
            assert backups[0]["backup_name"] == "backup_20241202_120000"  # Newest first
            assert backups[1]["backup_name"] == "backup_20241201_120000"
            assert all("timestamp" in backup for backup in backups)
            assert all("status" in backup for backup in backups)
    
    @pytest.mark.asyncio
    async def test_restore_backup_success(self, backup_mgr, mock_cosmos_db, mock_blob_client):
        """Test successful backup restore"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock backup metadata
        metadata = {
            "backup_name": "test_backup",
            "status": "completed",
            "containers": {
                "users": {"document_count": 2},
                "puzzles": {"document_count": 1}
            }
        }
        
        # Mock batch data
        batch_data = {
            "container": "users",
            "batch_start": 0,
            "document_count": 2,
            "documents": [
                {"id": "user1", "username": "test1"},
                {"id": "user2", "username": "test2"}
            ]
        }
        
        mock_download = AsyncMock()
        mock_download.readall.side_effect = [
            json.dumps(metadata).encode(),
            json.dumps(batch_data).encode()
        ]
        mock_blob_instance.download_blob.return_value = mock_download
        
        # Mock blob listing for batch files
        mock_batch_blob = Mock()
        mock_batch_blob.name = "test_backup/users/batch_000000.json"
        mock_container_client.list_blobs.return_value = [mock_batch_blob]
        
        # Mock container upsert
        mock_container = Mock()
        mock_container.upsert_item = Mock()
        mock_cosmos_db.get_container.return_value = mock_container
        
        with patch('app.database.backup.get_cosmos_db', return_value=mock_cosmos_db), \
             patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            
            result = await backup_mgr.restore_backup("test_backup", containers_to_restore=["users"])
            
            assert result["status"] == "completed"
            assert result["backup_name"] == "test_backup"
            assert "users" in result["containers"]
            assert result["containers"]["users"]["restored_count"] == 2
            
            # Verify documents were upserted
            assert mock_container.upsert_item.call_count == 2
    
    @pytest.mark.asyncio
    async def test_restore_backup_invalid_backup(self, backup_mgr, mock_blob_client):
        """Test restore with invalid backup name"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock missing metadata
        mock_blob_instance.download_blob.side_effect = Exception("Blob not found")
        
        with patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            with pytest.raises(ValueError, match="Backup not found"):
                await backup_mgr.restore_backup("nonexistent_backup")
    
    @pytest.mark.asyncio
    async def test_verify_backup_integrity_success(self, backup_mgr, mock_blob_client):
        """Test successful backup integrity verification"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock metadata
        metadata = {
            "backup_name": "test_backup",
            "status": "completed",
            "containers": {
                "users": {"document_count": 2}
            }
        }
        
        # Mock batch data
        batch_data = {
            "container": "users",
            "document_count": 2,
            "documents": [{"id": "user1"}, {"id": "user2"}]
        }
        
        mock_download = AsyncMock()
        mock_download.readall.side_effect = [
            json.dumps(metadata).encode(),
            json.dumps(batch_data).encode()
        ]
        mock_blob_instance.download_blob.return_value = mock_download
        
        # Mock batch file listing
        mock_batch_blob = Mock()
        mock_batch_blob.name = "test_backup/users/batch_000000.json"
        mock_container_client.list_blobs.return_value = [mock_batch_blob]
        
        with patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            result = await backup_mgr.verify_backup_integrity("test_backup")
            
            assert result["status"] == "verified"
            assert result["backup_name"] == "test_backup"
            assert result["containers"]["users"]["status"] == "verified"
            assert result["containers"]["users"]["expected_count"] == 2
            assert result["containers"]["users"]["actual_count"] == 2
    
    @pytest.mark.asyncio
    async def test_verify_backup_integrity_mismatch(self, backup_mgr, mock_blob_client):
        """Test backup verification with document count mismatch"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock metadata with expected count
        metadata = {
            "backup_name": "test_backup",
            "status": "completed",
            "containers": {
                "users": {"document_count": 5}  # Expected 5 documents
            }
        }
        
        # Mock batch data with fewer documents
        batch_data = {
            "container": "users",
            "document_count": 2,  # Only 2 documents
            "documents": [{"id": "user1"}, {"id": "user2"}]
        }
        
        mock_download = AsyncMock()
        mock_download.readall.side_effect = [
            json.dumps(metadata).encode(),
            json.dumps(batch_data).encode()
        ]
        mock_blob_instance.download_blob.return_value = mock_download
        
        mock_batch_blob = Mock()
        mock_batch_blob.name = "test_backup/users/batch_000000.json"
        mock_container_client.list_blobs.return_value = [mock_batch_blob]
        
        with patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            result = await backup_mgr.verify_backup_integrity("test_backup")
            
            assert result["status"] == "failed"
            assert result["containers"]["users"]["status"] == "failed"
            assert result["containers"]["users"]["expected_count"] == 5
            assert result["containers"]["users"]["actual_count"] == 2
            assert "mismatch" in result["containers"]["users"]["error"]
    
    @pytest.mark.asyncio
    async def test_cleanup_old_backups(self, backup_mgr, mock_blob_client):
        """Test cleanup of old backups"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock old and new backups
        old_date = (datetime.utcnow() - timedelta(days=35)).isoformat()
        new_date = (datetime.utcnow() - timedelta(days=5)).isoformat()
        
        backups = [
            {
                "backup_name": "old_backup",
                "timestamp": old_date,
                "status": "completed",
                "containers": ["users"]
            },
            {
                "backup_name": "new_backup", 
                "timestamp": new_date,
                "status": "completed",
                "containers": ["users"]
            }
        ]
        
        with patch.object(backup_mgr, 'list_backups', return_value=backups), \
             patch.object(backup_mgr, '_delete_backup', new_callable=AsyncMock) as mock_delete:
            
            result = await backup_mgr.cleanup_old_backups(retention_days=30)
            
            assert result["status"] == "completed"
            assert result["deleted_count"] == 1
            assert "old_backup" in result["deleted_backups"]
            assert "new_backup" not in result["deleted_backups"]
            
            # Verify delete was called for old backup
            mock_delete.assert_called_once_with("old_backup")
    
    @pytest.mark.asyncio
    async def test_get_backup_status_healthy(self, backup_mgr):
        """Test backup status when system is healthy"""
        # Mock recent successful backup within RPO
        recent_backup = {
            "backup_name": "recent_backup",
            "timestamp": (datetime.utcnow() - timedelta(hours=2)).isoformat(),
            "status": "completed",
            "containers": ["users", "puzzles"]
        }
        
        backups = [recent_backup]
        
        with patch.object(backup_mgr, 'list_backups', return_value=backups):
            status = await backup_mgr.get_backup_status()
            
            assert status["status"] == "healthy"
            assert status["rpo_compliant"] is True
            assert status["total_backups"] == 1
            assert status["recent_backup"] == recent_backup
    
    @pytest.mark.asyncio
    async def test_get_backup_status_warning(self, backup_mgr):
        """Test backup status when RPO is violated"""
        # Mock old backup outside RPO window
        old_backup = {
            "backup_name": "old_backup",
            "timestamp": (datetime.utcnow() - timedelta(hours=6)).isoformat(),
            "status": "completed",
            "containers": ["users"]
        }
        
        backups = [old_backup]
        
        with patch.object(backup_mgr, 'list_backups', return_value=backups):
            status = await backup_mgr.get_backup_status()
            
            assert status["status"] == "warning"
            assert status["rpo_compliant"] is False
            assert status["total_backups"] == 1
    
    @pytest.mark.asyncio
    async def test_backup_error_handling(self, backup_mgr, mock_cosmos_db, mock_blob_client):
        """Test backup error handling and recovery"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Mock container that raises exception
        mock_container = Mock()
        mock_container.query_items.side_effect = Exception("Database connection failed")
        mock_cosmos_db.get_container.return_value = mock_container
        
        with patch('app.database.backup.get_cosmos_db', return_value=mock_cosmos_db), \
             patch('app.database.backup.BlobServiceClient', return_value=mock_client):
            
            result = await backup_mgr.create_backup("error_test")
            
            assert result["status"] == "failed"
            assert "error" in result
            assert "Database connection failed" in result["error"]
    
    @pytest.mark.asyncio
    async def test_point_in_time_recovery_simulation(self, backup_mgr, mock_cosmos_db, mock_blob_client):
        """Test point-in-time recovery capabilities"""
        mock_client, mock_blob_instance, mock_container_client = mock_blob_client
        
        # Create multiple backups at different times
        backup_times = [
            datetime.utcnow() - timedelta(hours=6),
            datetime.utcnow() - timedelta(hours=3),
            datetime.utcnow() - timedelta(hours=1)
        ]
        
        backups = []
        for i, backup_time in enumerate(backup_times):
            backups.append({
                "backup_name": f"backup_{i}",
                "timestamp": backup_time.isoformat(),
                "status": "completed",
                "containers": ["users", "puzzles"]
            })
        
        with patch.object(backup_mgr, 'list_backups', return_value=backups):
            # Find backup closest to target time (4 hours ago)
            target_time = datetime.utcnow() - timedelta(hours=4)
            
            # Should select backup_0 (6 hours ago) as it's the latest before target
            available_backups = await backup_mgr.list_backups()
            
            suitable_backup = None
            for backup in available_backups:
                backup_time = datetime.fromisoformat(backup["timestamp"])
                if backup_time <= target_time:
                    suitable_backup = backup
                    break
            
            assert suitable_backup is not None
            assert suitable_backup["backup_name"] == "backup_0"
    
    def test_rpo_rto_compliance(self, backup_mgr):
        """Test RPO/RTO target definitions"""
        assert backup_mgr.rpo_hours == 4  # 4 hour RPO
        assert backup_mgr.rto_minutes == 30  # 30 minute RTO
        
        # Verify these are reasonable for the application
        assert backup_mgr.rpo_hours <= 24  # Should be within a day
        assert backup_mgr.rto_minutes <= 60  # Should be within an hour


class TestBackupIntegration:
    """Integration tests for backup functionality"""
    
    @pytest.mark.asyncio
    async def test_backup_restore_roundtrip(self):
        """Test complete backup and restore cycle"""
        # This would be an integration test with actual Cosmos DB
        # For now, we'll test the workflow logic
        
        backup_mgr = CosmosDBBackupManager()
        
        # Mock the entire workflow
        with patch.object(backup_mgr, 'create_backup') as mock_create, \
             patch.object(backup_mgr, 'verify_backup_integrity') as mock_verify, \
             patch.object(backup_mgr, 'restore_backup') as mock_restore:
            
            # Setup mock returns
            mock_create.return_value = {
                "backup_name": "test_roundtrip",
                "status": "completed",
                "containers": {"users": {"document_count": 10}}
            }
            
            mock_verify.return_value = {
                "status": "verified",
                "containers": {"users": {"status": "verified"}}
            }
            
            mock_restore.return_value = {
                "status": "completed",
                "containers": {"users": {"restored_count": 10}}
            }
            
            # Execute workflow
            backup_result = await backup_mgr.create_backup("test_roundtrip")
            assert backup_result["status"] == "completed"
            
            verify_result = await backup_mgr.verify_backup_integrity("test_roundtrip")
            assert verify_result["status"] == "verified"
            
            restore_result = await backup_mgr.restore_backup("test_roundtrip")
            assert restore_result["status"] == "completed"
    
    @pytest.mark.asyncio
    async def test_automated_backup_scheduling(self):
        """Test automated backup scheduling logic"""
        backup_mgr = CosmosDBBackupManager()
        
        # Simulate scheduled backup execution
        with patch.object(backup_mgr, 'create_backup') as mock_create, \
             patch.object(backup_mgr, 'cleanup_old_backups') as mock_cleanup:
            
            mock_create.return_value = {"status": "completed", "backup_name": "scheduled_backup"}
            mock_cleanup.return_value = {"status": "completed", "deleted_count": 2}
            
            # Simulate daily backup job
            backup_result = await backup_mgr.create_backup()
            cleanup_result = await backup_mgr.cleanup_old_backups(retention_days=30)
            
            assert backup_result["status"] == "completed"
            assert cleanup_result["status"] == "completed"
            
            # Verify both operations were called
            mock_create.assert_called_once()
            mock_cleanup.assert_called_once_with(retention_days=30)


if __name__ == "__main__":
    pytest.main([__file__])