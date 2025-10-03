"""
Azure Cosmos DB backup and recovery procedures
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import aiofiles
from azure.cosmos import CosmosClient, PartitionKey
from azure.cosmos.exceptions import CosmosHttpResponseError, CosmosResourceNotFoundError
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import BlobSasPermissions, generate_blob_sas

from app.config import settings
from app.database.connection import get_cosmos_db

logger = logging.getLogger(__name__)


class CosmosDBBackupManager:
    """Manages Cosmos DB backup and recovery operations"""
    
    def __init__(self):
        self.backup_storage_account = settings.azure_storage_account_name
        self.backup_container = "database-backups"
        self.rpo_hours = 4  # Recovery Point Objective: 4 hours
        self.rto_minutes = 30  # Recovery Time Objective: 30 minutes
        
    async def create_backup(self, backup_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a full backup of all Cosmos DB containers
        
        Args:
            backup_name: Optional custom backup name, defaults to timestamp
            
        Returns:
            Dict containing backup metadata and status
        """
        if not backup_name:
            backup_name = f"backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
            
        logger.info(f"Starting backup: {backup_name}")
        
        try:
            cosmos_db = await get_cosmos_db()
            backup_metadata = {
                "backup_name": backup_name,
                "timestamp": datetime.utcnow().isoformat(),
                "database": settings.cosmos_database_name,
                "containers": {},
                "status": "in_progress",
                "rpo_hours": self.rpo_hours,
                "rto_minutes": self.rto_minutes
            }
            
            # Backup each container
            containers = [
                settings.cosmos_container_users,
                settings.cosmos_container_puzzles,
                settings.cosmos_container_guesses
            ]
            
            for container_name in containers:
                logger.info(f"Backing up container: {container_name}")
                container_backup = await self._backup_container(
                    cosmos_db, container_name, backup_name
                )
                backup_metadata["containers"][container_name] = container_backup
            
            # Store backup metadata
            await self._store_backup_metadata(backup_name, backup_metadata)
            
            backup_metadata["status"] = "completed"
            logger.info(f"Backup completed successfully: {backup_name}")
            
            return backup_metadata
            
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            backup_metadata["status"] = "failed"
            backup_metadata["error"] = str(e)
            await self._store_backup_metadata(backup_name, backup_metadata)
            raise
    
    async def _backup_container(
        self, 
        cosmos_db, 
        container_name: str, 
        backup_name: str
    ) -> Dict[str, Any]:
        """Backup a single container"""
        container = cosmos_db.get_container(container_name)
        
        # Query all documents in the container
        query = "SELECT * FROM c"
        documents = []
        document_count = 0
        
        try:
            # Use async iteration to handle large datasets
            items = container.query_items(
                query=query,
                enable_cross_partition_query=True
            )
            
            for item in items:
                documents.append(item)
                document_count += 1
                
                # Process in batches to avoid memory issues
                if len(documents) >= 1000:
                    await self._store_container_batch(
                        backup_name, container_name, documents, document_count - len(documents)
                    )
                    documents = []
            
            # Store remaining documents
            if documents:
                await self._store_container_batch(
                    backup_name, container_name, documents, document_count - len(documents)
                )
            
            return {
                "document_count": document_count,
                "status": "completed",
                "backup_path": f"{backup_name}/{container_name}/"
            }
            
        except Exception as e:
            logger.error(f"Failed to backup container {container_name}: {e}")
            return {
                "document_count": document_count,
                "status": "failed",
                "error": str(e)
            }
    
    async def _store_container_batch(
        self, 
        backup_name: str, 
        container_name: str, 
        documents: List[Dict], 
        batch_start: int
    ) -> None:
        """Store a batch of documents to blob storage"""
        blob_name = f"{backup_name}/{container_name}/batch_{batch_start:06d}.json"
        
        # Convert documents to JSON
        batch_data = {
            "container": container_name,
            "batch_start": batch_start,
            "document_count": len(documents),
            "documents": documents
        }
        
        json_data = json.dumps(batch_data, indent=2, default=str)
        
        # Store to blob storage
        async with BlobServiceClient(
            account_url=f"https://{self.backup_storage_account}.blob.core.windows.net",
            credential=settings.azure_storage_account_key
        ) as blob_client:
            blob_client_instance = blob_client.get_blob_client(
                container=self.backup_container,
                blob=blob_name
            )
            
            await blob_client_instance.upload_blob(
                json_data.encode('utf-8'),
                overwrite=True
            )
    
    async def _store_backup_metadata(
        self, 
        backup_name: str, 
        metadata: Dict[str, Any]
    ) -> None:
        """Store backup metadata to blob storage"""
        blob_name = f"{backup_name}/metadata.json"
        json_data = json.dumps(metadata, indent=2, default=str)
        
        async with BlobServiceClient(
            account_url=f"https://{self.backup_storage_account}.blob.core.windows.net",
            credential=settings.azure_storage_account_key
        ) as blob_client:
            blob_client_instance = blob_client.get_blob_client(
                container=self.backup_container,
                blob=blob_name
            )
            
            await blob_client_instance.upload_blob(
                json_data.encode('utf-8'),
                overwrite=True
            )
    
    async def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        backups = []
        
        try:
            async with BlobServiceClient(
                account_url=f"https://{self.backup_storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                container_client = blob_client.get_container_client(self.backup_container)
                
                async for blob in container_client.list_blobs():
                    if blob.name.endswith('/metadata.json'):
                        backup_name = blob.name.split('/')[0]
                        
                        # Get metadata
                        blob_client_instance = blob_client.get_blob_client(
                            container=self.backup_container,
                            blob=blob.name
                        )
                        
                        content = await blob_client_instance.download_blob()
                        metadata = json.loads(await content.readall())
                        
                        backups.append({
                            "backup_name": backup_name,
                            "timestamp": metadata.get("timestamp"),
                            "status": metadata.get("status"),
                            "containers": list(metadata.get("containers", {}).keys()),
                            "size_bytes": blob.size
                        })
            
            # Sort by timestamp (newest first)
            backups.sort(key=lambda x: x["timestamp"], reverse=True)
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    async def restore_backup(
        self, 
        backup_name: str, 
        target_database: Optional[str] = None,
        containers_to_restore: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Restore from a backup
        
        Args:
            backup_name: Name of the backup to restore
            target_database: Target database name (defaults to current)
            containers_to_restore: List of containers to restore (defaults to all)
            
        Returns:
            Dict containing restore operation results
        """
        logger.info(f"Starting restore from backup: {backup_name}")
        
        try:
            # Get backup metadata
            metadata = await self._get_backup_metadata(backup_name)
            if not metadata:
                raise ValueError(f"Backup not found: {backup_name}")
            
            if metadata.get("status") != "completed":
                raise ValueError(f"Backup is not in completed state: {metadata.get('status')}")
            
            # Determine containers to restore
            available_containers = list(metadata["containers"].keys())
            if containers_to_restore is None:
                containers_to_restore = available_containers
            else:
                # Validate requested containers exist in backup
                invalid_containers = set(containers_to_restore) - set(available_containers)
                if invalid_containers:
                    raise ValueError(f"Containers not found in backup: {invalid_containers}")
            
            # Setup target database
            target_db = target_database or settings.cosmos_database_name
            cosmos_db = await get_cosmos_db()
            
            restore_results = {
                "backup_name": backup_name,
                "target_database": target_db,
                "timestamp": datetime.utcnow().isoformat(),
                "containers": {},
                "status": "in_progress"
            }
            
            # Restore each container
            for container_name in containers_to_restore:
                logger.info(f"Restoring container: {container_name}")
                container_result = await self._restore_container(
                    backup_name, container_name, cosmos_db
                )
                restore_results["containers"][container_name] = container_result
            
            restore_results["status"] = "completed"
            logger.info(f"Restore completed successfully: {backup_name}")
            
            return restore_results
            
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            restore_results["status"] = "failed"
            restore_results["error"] = str(e)
            raise
    
    async def _get_backup_metadata(self, backup_name: str) -> Optional[Dict[str, Any]]:
        """Get backup metadata from blob storage"""
        try:
            blob_name = f"{backup_name}/metadata.json"
            
            async with BlobServiceClient(
                account_url=f"https://{self.backup_storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                blob_client_instance = blob_client.get_blob_client(
                    container=self.backup_container,
                    blob=blob_name
                )
                
                content = await blob_client_instance.download_blob()
                return json.loads(await content.readall())
                
        except Exception as e:
            logger.error(f"Failed to get backup metadata: {e}")
            return None
    
    async def _restore_container(
        self, 
        backup_name: str, 
        container_name: str, 
        cosmos_db
    ) -> Dict[str, Any]:
        """Restore a single container from backup"""
        try:
            container = cosmos_db.get_container(container_name)
            restored_count = 0
            
            # List all batch files for this container
            async with BlobServiceClient(
                account_url=f"https://{self.backup_storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                container_client = blob_client.get_container_client(self.backup_container)
                
                batch_blobs = []
                async for blob in container_client.list_blobs(
                    name_starts_with=f"{backup_name}/{container_name}/"
                ):
                    if blob.name.endswith('.json') and 'batch_' in blob.name:
                        batch_blobs.append(blob.name)
                
                # Sort batch files to ensure proper order
                batch_blobs.sort()
                
                # Restore each batch
                for blob_name in batch_blobs:
                    blob_client_instance = blob_client.get_blob_client(
                        container=self.backup_container,
                        blob=blob_name
                    )
                    
                    content = await blob_client_instance.download_blob()
                    batch_data = json.loads(await content.readall())
                    
                    # Insert documents
                    for document in batch_data["documents"]:
                        try:
                            await asyncio.get_event_loop().run_in_executor(
                                None,
                                container.upsert_item,
                                document
                            )
                            restored_count += 1
                        except Exception as doc_error:
                            logger.warning(f"Failed to restore document {document.get('id')}: {doc_error}")
            
            return {
                "restored_count": restored_count,
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"Failed to restore container {container_name}: {e}")
            return {
                "restored_count": restored_count,
                "status": "failed",
                "error": str(e)
            }
    
    async def verify_backup_integrity(self, backup_name: str) -> Dict[str, Any]:
        """Verify the integrity of a backup"""
        logger.info(f"Verifying backup integrity: {backup_name}")
        
        try:
            metadata = await self._get_backup_metadata(backup_name)
            if not metadata:
                return {
                    "backup_name": backup_name,
                    "status": "failed",
                    "error": "Backup metadata not found"
                }
            
            verification_results = {
                "backup_name": backup_name,
                "timestamp": datetime.utcnow().isoformat(),
                "containers": {},
                "status": "in_progress"
            }
            
            # Verify each container
            for container_name, container_info in metadata["containers"].items():
                container_verification = await self._verify_container_backup(
                    backup_name, container_name, container_info
                )
                verification_results["containers"][container_name] = container_verification
            
            # Determine overall status
            all_verified = all(
                result["status"] == "verified" 
                for result in verification_results["containers"].values()
            )
            verification_results["status"] = "verified" if all_verified else "failed"
            
            return verification_results
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return {
                "backup_name": backup_name,
                "status": "failed",
                "error": str(e)
            }
    
    async def _verify_container_backup(
        self, 
        backup_name: str, 
        container_name: str, 
        container_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Verify a single container backup"""
        try:
            expected_count = container_info.get("document_count", 0)
            actual_count = 0
            
            # Count documents in all batch files
            async with BlobServiceClient(
                account_url=f"https://{self.backup_storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                container_client = blob_client.get_container_client(self.backup_container)
                
                async for blob in container_client.list_blobs(
                    name_starts_with=f"{backup_name}/{container_name}/"
                ):
                    if blob.name.endswith('.json') and 'batch_' in blob.name:
                        blob_client_instance = blob_client.get_blob_client(
                            container=self.backup_container,
                            blob=blob.name
                        )
                        
                        content = await blob_client_instance.download_blob()
                        batch_data = json.loads(await content.readall())
                        actual_count += batch_data.get("document_count", 0)
            
            if actual_count == expected_count:
                return {
                    "status": "verified",
                    "expected_count": expected_count,
                    "actual_count": actual_count
                }
            else:
                return {
                    "status": "failed",
                    "expected_count": expected_count,
                    "actual_count": actual_count,
                    "error": "Document count mismatch"
                }
                
        except Exception as e:
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def cleanup_old_backups(self, retention_days: int = 30) -> Dict[str, Any]:
        """Clean up backups older than retention period"""
        logger.info(f"Cleaning up backups older than {retention_days} days")
        
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            deleted_backups = []
            
            backups = await self.list_backups()
            
            for backup in backups:
                backup_date = datetime.fromisoformat(backup["timestamp"].replace('Z', '+00:00'))
                
                if backup_date < cutoff_date:
                    await self._delete_backup(backup["backup_name"])
                    deleted_backups.append(backup["backup_name"])
            
            return {
                "status": "completed",
                "deleted_count": len(deleted_backups),
                "deleted_backups": deleted_backups,
                "retention_days": retention_days
            }
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def _delete_backup(self, backup_name: str) -> None:
        """Delete a backup and all its files"""
        async with BlobServiceClient(
            account_url=f"https://{self.backup_storage_account}.blob.core.windows.net",
            credential=settings.azure_storage_account_key
        ) as blob_client:
            container_client = blob_client.get_container_client(self.backup_container)
            
            # Delete all blobs with this backup prefix
            async for blob in container_client.list_blobs(name_starts_with=f"{backup_name}/"):
                await container_client.delete_blob(blob.name)
    
    async def get_backup_status(self) -> Dict[str, Any]:
        """Get overall backup system status"""
        try:
            backups = await self.list_backups()
            
            # Find most recent successful backup
            recent_backup = None
            for backup in backups:
                if backup["status"] == "completed":
                    recent_backup = backup
                    break
            
            # Check if we're within RPO
            rpo_compliant = False
            if recent_backup:
                backup_time = datetime.fromisoformat(recent_backup["timestamp"].replace('Z', '+00:00'))
                time_since_backup = datetime.utcnow() - backup_time
                rpo_compliant = time_since_backup.total_seconds() / 3600 <= self.rpo_hours
            
            return {
                "status": "healthy" if rpo_compliant else "warning",
                "total_backups": len(backups),
                "recent_backup": recent_backup,
                "rpo_compliant": rpo_compliant,
                "rpo_hours": self.rpo_hours,
                "rto_minutes": self.rto_minutes
            }
            
        except Exception as e:
            logger.error(f"Failed to get backup status: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Global backup manager instance
backup_manager = CosmosDBBackupManager()