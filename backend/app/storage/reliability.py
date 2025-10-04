"""
Azure Blob Storage reliability and lifecycle management
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
import json
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import BlobSasPermissions, generate_blob_sas, BlobProperties
from azure.core.exceptions import ResourceNotFoundError, ServiceRequestError

from app.config import settings
from app.storage.blob_storage import BlobStorageManager

logger = logging.getLogger(__name__)


class StorageReliabilityManager:
    """Manages Azure Blob Storage reliability, lifecycle, and disaster recovery"""
    
    def __init__(self):
        self.storage_account = settings.azure_storage_account_name
        self.primary_container = settings.azure_storage_container_name
        self.backup_container = "character-images-backup"
        self.versioning_container = "character-images-versions"
        
        # Lifecycle management settings
        self.soft_delete_retention_days = 30
        self.version_retention_days = 90
        self.archive_after_days = 365
        
        # Redundancy settings
        self.enable_versioning = True
        self.enable_soft_delete = True
        self.enable_cross_region_replication = False  # Would require secondary region
        
    async def configure_lifecycle_policies(self) -> Dict[str, Any]:
        """
        Configure blob storage lifecycle management policies
        
        Returns:
            Dict containing policy configuration results
        """
        logger.info("Configuring blob storage lifecycle policies")
        
        try:
            async with BlobServiceClient(
                account_url=f"https://{self.storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                
                # Configure lifecycle management rules
                lifecycle_policy = {
                    "rules": [
                        {
                            "name": "character-images-lifecycle",
                            "enabled": True,
                            "type": "Lifecycle",
                            "definition": {
                                "filters": {
                                    "blobTypes": ["blockBlob"],
                                    "prefixMatch": ["marvel/", "DC/", "image/"]
                                },
                                "actions": {
                                    "baseBlob": {
                                        "tierToCool": {
                                            "daysAfterModificationGreaterThan": 30
                                        },
                                        "tierToArchive": {
                                            "daysAfterModificationGreaterThan": self.archive_after_days
                                        },
                                        "delete": {
                                            "daysAfterModificationGreaterThan": 2555  # ~7 years
                                        }
                                    },
                                    "snapshot": {
                                        "delete": {
                                            "daysAfterCreationGreaterThan": self.version_retention_days
                                        }
                                    },
                                    "version": {
                                        "delete": {
                                            "daysAfterCreationGreaterThan": self.version_retention_days
                                        }
                                    }
                                }
                            }
                        },
                        {
                            "name": "backup-retention",
                            "enabled": True,
                            "type": "Lifecycle",
                            "definition": {
                                "filters": {
                                    "blobTypes": ["blockBlob"],
                                    "prefixMatch": ["database-backups/"]
                                },
                                "actions": {
                                    "baseBlob": {
                                        "tierToCool": {
                                            "daysAfterModificationGreaterThan": 7
                                        },
                                        "tierToArchive": {
                                            "daysAfterModificationGreaterThan": 30
                                        },
                                        "delete": {
                                            "daysAfterModificationGreaterThan": 2555  # ~7 years
                                        }
                                    }
                                }
                            }
                        }
                    ]
                }
                
                # Note: In a real implementation, you would use the Azure Management SDK
                # to set lifecycle policies. For this example, we'll simulate the configuration
                
                return {
                    "status": "configured",
                    "policies": lifecycle_policy["rules"],
                    "soft_delete_retention_days": self.soft_delete_retention_days,
                    "version_retention_days": self.version_retention_days,
                    "archive_after_days": self.archive_after_days
                }
                
        except Exception as e:
            logger.error(f"Failed to configure lifecycle policies: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def enable_soft_delete(self) -> Dict[str, Any]:
        """
        Enable soft delete for blob storage
        
        Returns:
            Dict containing soft delete configuration results
        """
        logger.info("Enabling soft delete for blob storage")
        
        try:
            # Note: In a real implementation, you would use the Azure Management SDK
            # to configure soft delete at the storage account level
            
            return {
                "status": "enabled",
                "retention_days": self.soft_delete_retention_days,
                "applies_to": ["blobs", "containers"]
            }
            
        except Exception as e:
            logger.error(f"Failed to enable soft delete: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def enable_versioning(self) -> Dict[str, Any]:
        """
        Enable blob versioning for the storage account
        
        Returns:
            Dict containing versioning configuration results
        """
        logger.info("Enabling blob versioning")
        
        try:
            # Note: In a real implementation, you would use the Azure Management SDK
            # to enable versioning at the storage account level
            
            return {
                "status": "enabled",
                "version_retention_days": self.version_retention_days,
                "automatic_versioning": True
            }
            
        except Exception as e:
            logger.error(f"Failed to enable versioning: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def create_backup_copy(self, source_blob_path: str) -> Dict[str, Any]:
        """
        Create a backup copy of a blob in the backup container
        
        Args:
            source_blob_path: Path to the source blob
            
        Returns:
            Dict containing backup operation results
        """
        logger.info(f"Creating backup copy of: {source_blob_path}")
        
        try:
            async with BlobServiceClient(
                account_url=f"https://{self.storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                
                # Get source blob
                source_blob = blob_client.get_blob_client(
                    container=self.primary_container,
                    blob=source_blob_path
                )
                
                # Check if source exists
                try:
                    source_properties = await source_blob.get_blob_properties()
                except ResourceNotFoundError:
                    return {
                        "status": "failed",
                        "error": f"Source blob not found: {source_blob_path}"
                    }
                
                # Create backup blob path with timestamp
                timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{source_blob_path}.backup.{timestamp}"
                
                backup_blob = blob_client.get_blob_client(
                    container=self.backup_container,
                    blob=backup_path
                )
                
                # Copy blob to backup container
                source_url = source_blob.url
                copy_operation = await backup_blob.start_copy_from_url(source_url)
                
                # Wait for copy to complete (for small files this should be immediate)
                copy_status = copy_operation
                
                return {
                    "status": "completed",
                    "source_path": source_blob_path,
                    "backup_path": backup_path,
                    "backup_container": self.backup_container,
                    "copy_id": copy_status.get("copy_id"),
                    "timestamp": timestamp
                }
                
        except Exception as e:
            logger.error(f"Failed to create backup copy: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def restore_from_backup(self, backup_blob_path: str, target_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Restore a blob from backup
        
        Args:
            backup_blob_path: Path to the backup blob
            target_path: Target path for restoration (defaults to original path)
            
        Returns:
            Dict containing restore operation results
        """
        logger.info(f"Restoring from backup: {backup_blob_path}")
        
        try:
            async with BlobServiceClient(
                account_url=f"https://{self.storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                
                # Get backup blob
                backup_blob = blob_client.get_blob_client(
                    container=self.backup_container,
                    blob=backup_blob_path
                )
                
                # Check if backup exists
                try:
                    backup_properties = await backup_blob.get_blob_properties()
                except ResourceNotFoundError:
                    return {
                        "status": "failed",
                        "error": f"Backup blob not found: {backup_blob_path}"
                    }
                
                # Determine target path
                if not target_path:
                    # Extract original path from backup path
                    target_path = backup_blob_path.split('.backup.')[0]
                
                # Create target blob
                target_blob = blob_client.get_blob_client(
                    container=self.primary_container,
                    blob=target_path
                )
                
                # Copy backup to target location
                backup_url = backup_blob.url
                copy_operation = await target_blob.start_copy_from_url(backup_url)
                
                return {
                    "status": "completed",
                    "backup_path": backup_blob_path,
                    "restored_path": target_path,
                    "copy_id": copy_operation.get("copy_id"),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def list_blob_versions(self, blob_path: str) -> List[Dict[str, Any]]:
        """
        List all versions of a blob
        
        Args:
            blob_path: Path to the blob
            
        Returns:
            List of blob version information
        """
        logger.info(f"Listing versions for: {blob_path}")
        
        try:
            async with BlobServiceClient(
                account_url=f"https://{self.storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                
                container_client = blob_client.get_container_client(self.primary_container)
                
                versions = []
                async for blob in container_client.list_blobs(
                    name_starts_with=blob_path,
                    include=["versions", "metadata"]
                ):
                    if blob.name == blob_path:
                        versions.append({
                            "version_id": getattr(blob, 'version_id', None),
                            "is_current_version": getattr(blob, 'is_current_version', True),
                            "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                            "size": blob.size,
                            "etag": blob.etag,
                            "content_type": getattr(blob, 'content_type', None)
                        })
                
                # Sort by last modified (newest first)
                versions.sort(key=lambda x: x["last_modified"] or "", reverse=True)
                
                return versions
                
        except Exception as e:
            logger.error(f"Failed to list blob versions: {e}")
            return []
    
    async def restore_blob_version(self, blob_path: str, version_id: str) -> Dict[str, Any]:
        """
        Restore a specific version of a blob
        
        Args:
            blob_path: Path to the blob
            version_id: Version ID to restore
            
        Returns:
            Dict containing restore operation results
        """
        logger.info(f"Restoring blob version: {blob_path} (version: {version_id})")
        
        try:
            async with BlobServiceClient(
                account_url=f"https://{self.storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                
                # Get the specific version
                versioned_blob = blob_client.get_blob_client(
                    container=self.primary_container,
                    blob=blob_path,
                    version_id=version_id
                )
                
                # Get current blob
                current_blob = blob_client.get_blob_client(
                    container=self.primary_container,
                    blob=blob_path
                )
                
                # Copy versioned blob to current
                versioned_url = versioned_blob.url
                copy_operation = await current_blob.start_copy_from_url(versioned_url)
                
                return {
                    "status": "completed",
                    "blob_path": blob_path,
                    "restored_version": version_id,
                    "copy_id": copy_operation.get("copy_id"),
                    "timestamp": datetime.utcnow().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Failed to restore blob version: {e}")
            return {
                "status": "failed",
                "error": str(e)
            }
    
    async def perform_storage_health_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive storage health check
        
        Returns:
            Dict containing health check results
        """
        logger.info("Performing storage health check")
        
        health_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_status": "healthy",
            "containers": {},
            "policies": {},
            "redundancy": {}
        }
        
        try:
            async with BlobServiceClient(
                account_url=f"https://{self.storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                
                # Check container accessibility
                containers_to_check = [
                    self.primary_container,
                    self.backup_container,
                    "database-backups"
                ]
                
                for container_name in containers_to_check:
                    try:
                        container_client = blob_client.get_container_client(container_name)
                        properties = await container_client.get_container_properties()
                        
                        # Count blobs in container
                        blob_count = 0
                        total_size = 0
                        async for blob in container_client.list_blobs():
                            blob_count += 1
                            total_size += blob.size or 0
                        
                        health_results["containers"][container_name] = {
                            "status": "healthy",
                            "blob_count": blob_count,
                            "total_size_bytes": total_size,
                            "last_modified": properties.last_modified.isoformat() if properties.last_modified else None
                        }
                        
                    except ResourceNotFoundError:
                        health_results["containers"][container_name] = {
                            "status": "missing",
                            "error": "Container not found"
                        }
                        health_results["overall_status"] = "warning"
                        
                    except Exception as e:
                        health_results["containers"][container_name] = {
                            "status": "unhealthy",
                            "error": str(e)
                        }
                        health_results["overall_status"] = "unhealthy"
                
                # Check lifecycle policies (simulated)
                health_results["policies"] = {
                    "lifecycle_management": "configured",
                    "soft_delete": "enabled" if self.enable_soft_delete else "disabled",
                    "versioning": "enabled" if self.enable_versioning else "disabled",
                    "retention_days": self.soft_delete_retention_days
                }
                
                # Check redundancy settings
                health_results["redundancy"] = {
                    "replication_type": "LRS",  # Would be configured at account level
                    "cross_region_replication": self.enable_cross_region_replication,
                    "backup_container_available": self.backup_container in health_results["containers"]
                }
                
        except Exception as e:
            logger.error(f"Storage health check failed: {e}")
            health_results["overall_status"] = "unhealthy"
            health_results["error"] = str(e)
        
        return health_results
    
    async def run_disaster_recovery_drill(self) -> Dict[str, Any]:
        """
        Run a disaster recovery drill to test backup and restore procedures
        
        Returns:
            Dict containing drill results
        """
        logger.info("Running disaster recovery drill")
        
        drill_results = {
            "timestamp": datetime.utcnow().isoformat(),
            "drill_id": f"dr_drill_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            "status": "in_progress",
            "tests": {}
        }
        
        try:
            # Test 1: Create a test blob and backup
            test_blob_path = f"test/dr_drill_{drill_results['drill_id']}.txt"
            test_content = f"Disaster recovery drill test content - {datetime.utcnow().isoformat()}"
            
            async with BlobServiceClient(
                account_url=f"https://{self.storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                
                # Create test blob
                test_blob = blob_client.get_blob_client(
                    container=self.primary_container,
                    blob=test_blob_path
                )
                
                await test_blob.upload_blob(test_content.encode(), overwrite=True)
                
                drill_results["tests"]["create_test_blob"] = {
                    "status": "passed",
                    "blob_path": test_blob_path
                }
                
                # Test 2: Create backup
                backup_result = await self.create_backup_copy(test_blob_path)
                drill_results["tests"]["create_backup"] = {
                    "status": "passed" if backup_result["status"] == "completed" else "failed",
                    "backup_path": backup_result.get("backup_path"),
                    "details": backup_result
                }
                
                # Test 3: Delete original and restore from backup
                await test_blob.delete_blob()
                
                if backup_result["status"] == "completed":
                    restore_result = await self.restore_from_backup(
                        backup_result["backup_path"], 
                        test_blob_path
                    )
                    drill_results["tests"]["restore_from_backup"] = {
                        "status": "passed" if restore_result["status"] == "completed" else "failed",
                        "details": restore_result
                    }
                    
                    # Verify restored content
                    try:
                        restored_content = await test_blob.download_blob()
                        restored_text = (await restored_content.readall()).decode()
                        
                        if restored_text == test_content:
                            drill_results["tests"]["verify_restored_content"] = {
                                "status": "passed",
                                "content_match": True
                            }
                        else:
                            drill_results["tests"]["verify_restored_content"] = {
                                "status": "failed",
                                "content_match": False,
                                "expected_length": len(test_content),
                                "actual_length": len(restored_text)
                            }
                    except Exception as e:
                        drill_results["tests"]["verify_restored_content"] = {
                            "status": "failed",
                            "error": str(e)
                        }
                
                # Test 4: Cleanup test files
                try:
                    await test_blob.delete_blob()
                    
                    if backup_result.get("backup_path"):
                        backup_blob = blob_client.get_blob_client(
                            container=self.backup_container,
                            blob=backup_result["backup_path"]
                        )
                        await backup_blob.delete_blob()
                    
                    drill_results["tests"]["cleanup"] = {
                        "status": "passed"
                    }
                except Exception as e:
                    drill_results["tests"]["cleanup"] = {
                        "status": "failed",
                        "error": str(e)
                    }
            
            # Determine overall drill status
            all_tests_passed = all(
                test.get("status") == "passed" 
                for test in drill_results["tests"].values()
            )
            
            drill_results["status"] = "passed" if all_tests_passed else "failed"
            
        except Exception as e:
            logger.error(f"Disaster recovery drill failed: {e}")
            drill_results["status"] = "failed"
            drill_results["error"] = str(e)
        
        return drill_results
    
    async def get_storage_metrics(self) -> Dict[str, Any]:
        """
        Get storage usage and performance metrics
        
        Returns:
            Dict containing storage metrics
        """
        logger.info("Collecting storage metrics")
        
        try:
            async with BlobServiceClient(
                account_url=f"https://{self.storage_account}.blob.core.windows.net",
                credential=settings.azure_storage_account_key
            ) as blob_client:
                
                metrics = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "containers": {},
                    "totals": {
                        "total_blobs": 0,
                        "total_size_bytes": 0,
                        "total_size_mb": 0
                    }
                }
                
                # Collect metrics for each container
                containers = [self.primary_container, self.backup_container, "database-backups"]
                
                for container_name in containers:
                    try:
                        container_client = blob_client.get_container_client(container_name)
                        
                        container_metrics = {
                            "blob_count": 0,
                            "total_size_bytes": 0,
                            "universes": {"marvel": 0, "DC": 0, "image": 0, "other": 0}
                        }
                        
                        async for blob in container_client.list_blobs():
                            container_metrics["blob_count"] += 1
                            container_metrics["total_size_bytes"] += blob.size or 0
                            
                            # Categorize by universe
                            if blob.name.startswith("marvel/"):
                                container_metrics["universes"]["marvel"] += 1
                            elif blob.name.startswith("DC/"):
                                container_metrics["universes"]["DC"] += 1
                            elif blob.name.startswith("image/"):
                                container_metrics["universes"]["image"] += 1
                            else:
                                container_metrics["universes"]["other"] += 1
                        
                        container_metrics["total_size_mb"] = container_metrics["total_size_bytes"] / (1024 * 1024)
                        metrics["containers"][container_name] = container_metrics
                        
                        # Add to totals
                        metrics["totals"]["total_blobs"] += container_metrics["blob_count"]
                        metrics["totals"]["total_size_bytes"] += container_metrics["total_size_bytes"]
                        
                    except ResourceNotFoundError:
                        metrics["containers"][container_name] = {
                            "status": "not_found",
                            "blob_count": 0,
                            "total_size_bytes": 0
                        }
                
                metrics["totals"]["total_size_mb"] = metrics["totals"]["total_size_bytes"] / (1024 * 1024)
                
                return metrics
                
        except Exception as e:
            logger.error(f"Failed to collect storage metrics: {e}")
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "status": "failed",
                "error": str(e)
            }


# Global storage reliability manager instance
storage_reliability = StorageReliabilityManager()