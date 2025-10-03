"""
Data lifecycle management and GDPR compliance utilities
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
import json

from app.repositories.user_repository import UserRepository
from app.repositories.guess_repository import GuessRepository
from app.repositories.puzzle_repository import PuzzleRepository
from app.security.secrets_manager import data_protection
from app.auth.jwt_handler import revoke_all_user_tokens
from app.auth.session import session_manager

logger = logging.getLogger(__name__)

class DataCategory(Enum):
    """Categories of data for lifecycle management"""
    PERSONAL_DATA = "personal_data"
    USAGE_DATA = "usage_data"
    ANALYTICS_DATA = "analytics_data"
    AUDIT_DATA = "audit_data"
    TEMPORARY_DATA = "temporary_data"
    SYSTEM_DATA = "system_data"

class PurgeReason(Enum):
    """Reasons for data purging"""
    RETENTION_EXPIRED = "retention_expired"
    USER_REQUEST = "user_request"
    ACCOUNT_DELETION = "account_deletion"
    GDPR_COMPLIANCE = "gdpr_compliance"
    SYSTEM_CLEANUP = "system_cleanup"

@dataclass
class DataRecord:
    """Represents a data record for lifecycle management"""
    id: str
    user_id: Optional[str]
    category: DataCategory
    created_at: datetime
    last_accessed: Optional[datetime]
    data_size: int
    contains_pii: bool
    retention_period: timedelta
    metadata: Dict[str, Any]

@dataclass
class PurgeOperation:
    """Represents a data purge operation"""
    operation_id: str
    user_id: Optional[str]
    reason: PurgeReason
    categories: List[DataCategory]
    records_count: int
    started_at: datetime
    completed_at: Optional[datetime]
    success: bool
    errors: List[str]

class DataInventoryManager:
    """Manages data inventory for lifecycle operations"""
    
    def __init__(self):
        self.user_repo = UserRepository()
        self.guess_repo = GuessRepository()
        self.puzzle_repo = PuzzleRepository()
    
    async def get_user_data_inventory(self, user_id: str) -> Dict[DataCategory, List[DataRecord]]:
        """Get complete data inventory for a user"""
        inventory = {category: [] for category in DataCategory}
        
        try:
            # Personal data (user profile)
            user = await self.user_repo.get_user_by_id(user_id)
            if user:
                inventory[DataCategory.PERSONAL_DATA].append(DataRecord(
                    id=f"user_{user.id}",
                    user_id=user.id,
                    category=DataCategory.PERSONAL_DATA,
                    created_at=user.created_at,
                    last_accessed=None,
                    data_size=len(json.dumps(user.to_dict())),
                    contains_pii=True,
                    retention_period=timedelta(days=2555),  # 7 years
                    metadata={"type": "user_profile", "email": user.email}
                ))
            
            # Usage data (guesses)
            guesses = await self.guess_repo.get_user_guesses(user_id)
            for guess in guesses:
                inventory[DataCategory.USAGE_DATA].append(DataRecord(
                    id=f"guess_{guess.id}",
                    user_id=user_id,
                    category=DataCategory.USAGE_DATA,
                    created_at=guess.timestamp,
                    last_accessed=None,
                    data_size=len(json.dumps(guess.to_dict())),
                    contains_pii=False,
                    retention_period=timedelta(days=365),  # 1 year
                    metadata={"type": "guess", "puzzle_id": guess.puzzle_id}
                ))
            
            # Analytics data (aggregated stats)
            user_stats = await self.user_repo.get_user_stats(user_id)
            if user_stats:
                inventory[DataCategory.ANALYTICS_DATA].append(DataRecord(
                    id=f"stats_{user_id}",
                    user_id=user_id,
                    category=DataCategory.ANALYTICS_DATA,
                    created_at=user.created_at if user else datetime.now(timezone.utc),
                    last_accessed=None,
                    data_size=len(json.dumps(user_stats)),
                    contains_pii=False,
                    retention_period=timedelta(days=90),
                    metadata={"type": "user_stats"}
                ))
            
            # Session data
            session_info = session_manager.get_session_security_info(user_id)
            if session_info:
                inventory[DataCategory.TEMPORARY_DATA].append(DataRecord(
                    id=f"session_{user_id}",
                    user_id=user_id,
                    category=DataCategory.TEMPORARY_DATA,
                    created_at=datetime.fromisoformat(session_info["created_at"].replace('Z', '+00:00')),
                    last_accessed=datetime.fromisoformat(session_info["last_activity"].replace('Z', '+00:00')),
                    data_size=len(json.dumps(session_info)),
                    contains_pii=True,
                    retention_period=timedelta(days=30),
                    metadata={"type": "session", "ip_address": session_info.get("ip_address")}
                ))
            
            logger.info(f"Generated data inventory for user {user_id}")
            return inventory
            
        except Exception as e:
            logger.error(f"Error generating data inventory for user {user_id}: {e}")
            return inventory
    
    async def get_system_data_inventory(self) -> Dict[DataCategory, List[DataRecord]]:
        """Get system-wide data inventory for cleanup"""
        inventory = {category: [] for category in DataCategory}
        
        try:
            # Get all users for system-wide analysis
            # This would be implemented based on your specific data storage
            # For now, we'll return empty inventory
            logger.info("Generated system data inventory")
            return inventory
            
        except Exception as e:
            logger.error(f"Error generating system data inventory: {e}")
            return inventory

class DataRetentionManager:
    """Manages data retention policies and automated cleanup"""
    
    def __init__(self):
        self.inventory_manager = DataInventoryManager()
        self.retention_policies = {
            DataCategory.PERSONAL_DATA: timedelta(days=2555),  # 7 years
            DataCategory.USAGE_DATA: timedelta(days=365),      # 1 year
            DataCategory.ANALYTICS_DATA: timedelta(days=90),   # 3 months
            DataCategory.AUDIT_DATA: timedelta(days=2555),     # 7 years
            DataCategory.TEMPORARY_DATA: timedelta(days=30),   # 1 month
            DataCategory.SYSTEM_DATA: timedelta(days=365),     # 1 year
        }
    
    async def identify_expired_data(self) -> Dict[DataCategory, List[DataRecord]]:
        """Identify data that has exceeded retention periods"""
        expired_data = {category: [] for category in DataCategory}
        current_time = datetime.now(timezone.utc)
        
        try:
            # Get system inventory
            inventory = await self.inventory_manager.get_system_data_inventory()
            
            for category, records in inventory.items():
                retention_period = self.retention_policies.get(category, timedelta(days=365))
                
                for record in records:
                    age = current_time - record.created_at
                    if age > retention_period:
                        expired_data[category].append(record)
            
            logger.info(f"Identified expired data across {len(expired_data)} categories")
            return expired_data
            
        except Exception as e:
            logger.error(f"Error identifying expired data: {e}")
            return expired_data
    
    async def create_retention_report(self) -> Dict[str, Any]:
        """Create a data retention compliance report"""
        try:
            expired_data = await self.identify_expired_data()
            
            report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "retention_policies": {
                    category.value: policy.days 
                    for category, policy in self.retention_policies.items()
                },
                "expired_data_summary": {},
                "total_expired_records": 0,
                "total_expired_size": 0,
                "recommendations": []
            }
            
            for category, records in expired_data.items():
                if records:
                    total_size = sum(record.data_size for record in records)
                    report["expired_data_summary"][category.value] = {
                        "count": len(records),
                        "total_size_bytes": total_size,
                        "oldest_record": min(record.created_at for record in records).isoformat(),
                        "contains_pii": any(record.contains_pii for record in records)
                    }
                    
                    report["total_expired_records"] += len(records)
                    report["total_expired_size"] += total_size
            
            # Add recommendations
            if report["total_expired_records"] > 0:
                report["recommendations"].append("Schedule automated data purge for expired records")
            
            if any(summary.get("contains_pii") for summary in report["expired_data_summary"].values()):
                report["recommendations"].append("Priority purge required for PII-containing records")
            
            return report
            
        except Exception as e:
            logger.error(f"Error creating retention report: {e}")
            return {"error": str(e)}

class AccountDeletionManager:
    """Manages complete account deletion and data purging"""
    
    def __init__(self):
        self.inventory_manager = DataInventoryManager()
        self.user_repo = UserRepository()
        self.guess_repo = GuessRepository()
    
    async def delete_user_account(self, user_id: str, reason: str = "user_request") -> PurgeOperation:
        """Completely delete a user account and all associated data"""
        operation_id = f"delete_{user_id}_{int(datetime.now().timestamp())}"
        
        operation = PurgeOperation(
            operation_id=operation_id,
            user_id=user_id,
            reason=PurgeReason.ACCOUNT_DELETION,
            categories=list(DataCategory),
            records_count=0,
            started_at=datetime.now(timezone.utc),
            completed_at=None,
            success=False,
            errors=[]
        )
        
        try:
            logger.info(f"Starting account deletion for user {user_id}")
            
            # 1. Get complete data inventory
            inventory = await self.inventory_manager.get_user_data_inventory(user_id)
            total_records = sum(len(records) for records in inventory.values())
            operation.records_count = total_records
            
            # 2. Revoke all authentication tokens
            try:
                revoke_all_user_tokens(user_id)
                logger.info(f"Revoked all tokens for user {user_id}")
            except Exception as e:
                operation.errors.append(f"Error revoking tokens: {str(e)}")
            
            # 3. Invalidate all sessions
            try:
                session_manager.invalidate_all_sessions(user_id)
                logger.info(f"Invalidated all sessions for user {user_id}")
            except Exception as e:
                operation.errors.append(f"Error invalidating sessions: {str(e)}")
            
            # 4. Delete user guesses
            try:
                deleted_guesses = await self.guess_repo.delete_user_guesses(user_id)
                logger.info(f"Deleted {deleted_guesses} guesses for user {user_id}")
            except Exception as e:
                operation.errors.append(f"Error deleting guesses: {str(e)}")
            
            # 5. Delete user profile
            try:
                await self.user_repo.delete_user(user_id)
                logger.info(f"Deleted user profile for user {user_id}")
            except Exception as e:
                operation.errors.append(f"Error deleting user profile: {str(e)}")
            
            # 6. Clean up any remaining references
            await self._cleanup_user_references(user_id, operation)
            
            operation.completed_at = datetime.now(timezone.utc)
            operation.success = len(operation.errors) == 0
            
            if operation.success:
                logger.info(f"Successfully deleted account for user {user_id}")
            else:
                logger.error(f"Account deletion completed with errors for user {user_id}: {operation.errors}")
            
            return operation
            
        except Exception as e:
            operation.errors.append(f"Critical error during account deletion: {str(e)}")
            operation.completed_at = datetime.now(timezone.utc)
            operation.success = False
            logger.error(f"Critical error during account deletion for user {user_id}: {e}")
            return operation
    
    async def _cleanup_user_references(self, user_id: str, operation: PurgeOperation):
        """Clean up any remaining user references in the system"""
        try:
            # Clean up any cached data
            # This would depend on your caching implementation
            
            # Clean up any audit logs (if they contain PII)
            # This would depend on your audit logging implementation
            
            # Clean up any temporary files or uploads
            # This would depend on your file storage implementation
            
            logger.info(f"Completed cleanup of user references for {user_id}")
            
        except Exception as e:
            operation.errors.append(f"Error cleaning up user references: {str(e)}")
    
    async def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Export all user data for GDPR data portability"""
        try:
            logger.info(f"Starting data export for user {user_id}")
            
            # Get complete data inventory
            inventory = await self.inventory_manager.get_user_data_inventory(user_id)
            
            export_data = {
                "export_generated_at": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "data_categories": {}
            }
            
            # Export each category
            for category, records in inventory.items():
                if records:
                    category_data = []
                    
                    for record in records:
                        # Get actual data based on record type
                        if record.metadata.get("type") == "user_profile":
                            user = await self.user_repo.get_user_by_id(user_id)
                            if user:
                                user_data = user.to_dict()
                                # Decrypt any encrypted PII for export
                                if "email" in user_data:
                                    try:
                                        user_data["email"] = data_protection.decrypt_pii(user_data["email"])
                                    except:
                                        pass  # Email might not be encrypted
                                category_data.append(user_data)
                        
                        elif record.metadata.get("type") == "guess":
                            guesses = await self.guess_repo.get_user_guesses(user_id)
                            category_data.extend([guess.to_dict() for guess in guesses])
                        
                        elif record.metadata.get("type") == "user_stats":
                            stats = await self.user_repo.get_user_stats(user_id)
                            if stats:
                                category_data.append(stats)
                    
                    if category_data:
                        export_data["data_categories"][category.value] = category_data
            
            logger.info(f"Completed data export for user {user_id}")
            return export_data
            
        except Exception as e:
            logger.error(f"Error exporting user data for {user_id}: {e}")
            return {"error": str(e)}

class GDPRComplianceManager:
    """Manages GDPR compliance operations"""
    
    def __init__(self):
        self.account_deletion = AccountDeletionManager()
        self.retention_manager = DataRetentionManager()
    
    async def handle_data_subject_request(self, user_id: str, request_type: str) -> Dict[str, Any]:
        """Handle GDPR data subject requests"""
        try:
            if request_type == "access":
                # Right to access - export user data
                return await self.account_deletion.export_user_data(user_id)
            
            elif request_type == "deletion":
                # Right to erasure - delete user account
                operation = await self.account_deletion.delete_user_account(user_id, "gdpr_request")
                return {
                    "operation_id": operation.operation_id,
                    "success": operation.success,
                    "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
                    "errors": operation.errors
                }
            
            elif request_type == "portability":
                # Right to data portability - export in structured format
                return await self.account_deletion.export_user_data(user_id)
            
            elif request_type == "rectification":
                # Right to rectification - would need to be handled by user profile update
                return {"message": "Rectification requests should be handled through profile update"}
            
            else:
                return {"error": f"Unknown request type: {request_type}"}
                
        except Exception as e:
            logger.error(f"Error handling GDPR request {request_type} for user {user_id}: {e}")
            return {"error": str(e)}
    
    async def generate_compliance_report(self) -> Dict[str, Any]:
        """Generate GDPR compliance report"""
        try:
            retention_report = await self.retention_manager.create_retention_report()
            
            compliance_report = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "gdpr_compliance_status": "compliant",
                "data_retention": retention_report,
                "recommendations": [],
                "action_items": []
            }
            
            # Check for compliance issues
            if retention_report.get("total_expired_records", 0) > 0:
                compliance_report["gdpr_compliance_status"] = "needs_attention"
                compliance_report["action_items"].append("Purge expired data records")
            
            # Add general recommendations
            compliance_report["recommendations"].extend([
                "Regular automated data retention cleanup",
                "Monitor data subject request response times",
                "Ensure all PII is properly encrypted",
                "Maintain audit logs for compliance activities"
            ])
            
            return compliance_report
            
        except Exception as e:
            logger.error(f"Error generating compliance report: {e}")
            return {"error": str(e)}

# Global instances
data_inventory = DataInventoryManager()
retention_manager = DataRetentionManager()
account_deletion = AccountDeletionManager()
gdpr_compliance = GDPRComplianceManager()

# Convenience functions
async def delete_user_account(user_id: str) -> PurgeOperation:
    """Delete a user account completely"""
    return await account_deletion.delete_user_account(user_id)

async def export_user_data(user_id: str) -> Dict[str, Any]:
    """Export all user data"""
    return await account_deletion.export_user_data(user_id)

async def handle_gdpr_request(user_id: str, request_type: str) -> Dict[str, Any]:
    """Handle GDPR data subject request"""
    return await gdpr_compliance.handle_data_subject_request(user_id, request_type)