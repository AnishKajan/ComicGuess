"""
Azure Key Vault secrets management and data protection utilities
"""

import os
import logging
import json
import hashlib
import secrets
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from enum import Enum
import asyncio

try:
    from azure.keyvault.secrets import SecretClient
    from azure.identity import DefaultAzureCredential, ClientSecretCredential
    from azure.core.exceptions import ResourceNotFoundError
    AZURE_AVAILABLE = True
except ImportError:
    AZURE_AVAILABLE = False
    SecretClient = None
    DefaultAzureCredential = None
    ClientSecretCredential = None
    ResourceNotFoundError = Exception

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

logger = logging.getLogger(__name__)

class SecretType(Enum):
    """Types of secrets managed by the system"""
    DATABASE_CONNECTION = "database-connection"
    JWT_SECRET = "jwt-secret"
    API_KEY = "api-key"
    ENCRYPTION_KEY = "encryption-key"
    OAUTH_CLIENT_SECRET = "oauth-client-secret"
    WEBHOOK_SECRET = "webhook-secret"
    CAPTCHA_SECRET = "captcha-secret"

@dataclass
class SecretMetadata:
    """Metadata for a managed secret"""
    name: str
    secret_type: SecretType
    created_at: datetime
    last_rotated: datetime
    rotation_interval: timedelta
    is_encrypted: bool = True
    tags: Dict[str, str] = None

class LocalSecretsStore:
    """Local fallback secrets store when Azure Key Vault is not available"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        self.secrets: Dict[str, str] = {}
        self.metadata: Dict[str, SecretMetadata] = {}
        
        # Initialize encryption
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Generate a key from environment or create new one
            key = os.getenv('LOCAL_SECRETS_KEY')
            if not key:
                key = Fernet.generate_key().decode()
                logger.warning("Generated new local secrets key. Set LOCAL_SECRETS_KEY environment variable for persistence.")
            self.fernet = Fernet(key.encode())
    
    def set_secret(self, name: str, value: str, metadata: Optional[SecretMetadata] = None) -> bool:
        """Store a secret locally with encryption"""
        try:
            encrypted_value = self.fernet.encrypt(value.encode()).decode()
            self.secrets[name] = encrypted_value
            
            if metadata:
                self.metadata[name] = metadata
            
            logger.info(f"Stored secret locally: {name}")
            return True
        except Exception as e:
            logger.error(f"Error storing local secret {name}: {e}")
            return False
    
    def get_secret(self, name: str) -> Optional[str]:
        """Retrieve and decrypt a secret"""
        try:
            encrypted_value = self.secrets.get(name)
            if encrypted_value:
                return self.fernet.decrypt(encrypted_value.encode()).decode()
            return None
        except Exception as e:
            logger.error(f"Error retrieving local secret {name}: {e}")
            return None
    
    def delete_secret(self, name: str) -> bool:
        """Delete a secret"""
        try:
            if name in self.secrets:
                del self.secrets[name]
            if name in self.metadata:
                del self.metadata[name]
            return True
        except Exception as e:
            logger.error(f"Error deleting local secret {name}: {e}")
            return False
    
    def list_secrets(self) -> List[str]:
        """List all secret names"""
        return list(self.secrets.keys())

class AzureKeyVaultManager:
    """Azure Key Vault integration for secrets management"""
    
    def __init__(self, vault_url: str, credential=None):
        if not AZURE_AVAILABLE:
            raise ImportError("Azure SDK not available. Install azure-keyvault-secrets and azure-identity")
        
        self.vault_url = vault_url
        self.credential = credential or DefaultAzureCredential()
        self.client = SecretClient(vault_url=vault_url, credential=self.credential)
        self.metadata_cache: Dict[str, SecretMetadata] = {}
    
    async def set_secret(self, name: str, value: str, metadata: Optional[SecretMetadata] = None) -> bool:
        """Store a secret in Azure Key Vault"""
        try:
            # Prepare tags for metadata
            tags = {}
            if metadata:
                tags.update({
                    "secret_type": metadata.secret_type.value,
                    "created_at": metadata.created_at.isoformat(),
                    "last_rotated": metadata.last_rotated.isoformat(),
                    "rotation_interval_days": str(metadata.rotation_interval.days),
                    "is_encrypted": str(metadata.is_encrypted)
                })
                if metadata.tags:
                    tags.update(metadata.tags)
            
            # Store secret
            secret = self.client.set_secret(name, value, tags=tags)
            
            # Cache metadata
            if metadata:
                self.metadata_cache[name] = metadata
            
            logger.info(f"Stored secret in Azure Key Vault: {name}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing secret in Azure Key Vault {name}: {e}")
            return False
    
    async def get_secret(self, name: str) -> Optional[str]:
        """Retrieve a secret from Azure Key Vault"""
        try:
            secret = self.client.get_secret(name)
            return secret.value
        except ResourceNotFoundError:
            logger.warning(f"Secret not found in Azure Key Vault: {name}")
            return None
        except Exception as e:
            logger.error(f"Error retrieving secret from Azure Key Vault {name}: {e}")
            return None
    
    async def delete_secret(self, name: str) -> bool:
        """Delete a secret from Azure Key Vault"""
        try:
            delete_operation = self.client.begin_delete_secret(name)
            delete_operation.wait()
            
            # Remove from cache
            if name in self.metadata_cache:
                del self.metadata_cache[name]
            
            logger.info(f"Deleted secret from Azure Key Vault: {name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting secret from Azure Key Vault {name}: {e}")
            return False
    
    async def list_secrets(self) -> List[str]:
        """List all secret names in Azure Key Vault"""
        try:
            secret_properties = self.client.list_properties_of_secrets()
            return [secret.name for secret in secret_properties]
        except Exception as e:
            logger.error(f"Error listing secrets from Azure Key Vault: {e}")
            return []
    
    async def rotate_secret(self, name: str, new_value: str) -> bool:
        """Rotate a secret with versioning"""
        try:
            # Get current metadata
            metadata = self.metadata_cache.get(name)
            if metadata:
                metadata.last_rotated = datetime.now(timezone.utc)
            
            # Store new version
            return await self.set_secret(name, new_value, metadata)
        except Exception as e:
            logger.error(f"Error rotating secret {name}: {e}")
            return False

class SecretsManager:
    """Unified secrets management with Azure Key Vault and local fallback"""
    
    def __init__(self):
        self.azure_manager: Optional[AzureKeyVaultManager] = None
        self.local_store = LocalSecretsStore()
        self.use_azure = False
        
        # Initialize Azure Key Vault if configured
        vault_url = os.getenv('AZURE_KEYVAULT_URL')
        if vault_url and AZURE_AVAILABLE:
            try:
                self.azure_manager = AzureKeyVaultManager(vault_url)
                self.use_azure = True
                logger.info("Initialized Azure Key Vault secrets manager")
            except Exception as e:
                logger.warning(f"Failed to initialize Azure Key Vault, using local store: {e}")
        else:
            logger.info("Using local secrets store")
        
        # Secret rotation tracking
        self.rotation_schedule: Dict[str, SecretMetadata] = {}
    
    async def set_secret(self, name: str, value: str, secret_type: SecretType = SecretType.API_KEY,
                        rotation_interval: timedelta = timedelta(days=90),
                        tags: Optional[Dict[str, str]] = None) -> bool:
        """Store a secret with metadata"""
        try:
            # Create metadata
            metadata = SecretMetadata(
                name=name,
                secret_type=secret_type,
                created_at=datetime.now(timezone.utc),
                last_rotated=datetime.now(timezone.utc),
                rotation_interval=rotation_interval,
                tags=tags or {}
            )
            
            # Store secret
            if self.use_azure and self.azure_manager:
                success = await self.azure_manager.set_secret(name, value, metadata)
            else:
                success = self.local_store.set_secret(name, value, metadata)
            
            if success:
                # Schedule rotation
                self.rotation_schedule[name] = metadata
                logger.info(f"Secret stored successfully: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error storing secret {name}: {e}")
            return False
    
    async def get_secret(self, name: str) -> Optional[str]:
        """Retrieve a secret"""
        try:
            if self.use_azure and self.azure_manager:
                return await self.azure_manager.get_secret(name)
            else:
                return self.local_store.get_secret(name)
        except Exception as e:
            logger.error(f"Error retrieving secret {name}: {e}")
            return None
    
    async def delete_secret(self, name: str) -> bool:
        """Delete a secret"""
        try:
            if self.use_azure and self.azure_manager:
                success = await self.azure_manager.delete_secret(name)
            else:
                success = self.local_store.delete_secret(name)
            
            if success and name in self.rotation_schedule:
                del self.rotation_schedule[name]
            
            return success
        except Exception as e:
            logger.error(f"Error deleting secret {name}: {e}")
            return False
    
    async def rotate_secret(self, name: str, new_value: Optional[str] = None) -> bool:
        """Rotate a secret (generate new value if not provided)"""
        try:
            metadata = self.rotation_schedule.get(name)
            if not metadata:
                logger.error(f"No metadata found for secret rotation: {name}")
                return False
            
            # Generate new value if not provided
            if new_value is None:
                if metadata.secret_type == SecretType.JWT_SECRET:
                    new_value = secrets.token_urlsafe(64)
                elif metadata.secret_type == SecretType.API_KEY:
                    new_value = secrets.token_urlsafe(32)
                elif metadata.secret_type == SecretType.ENCRYPTION_KEY:
                    new_value = Fernet.generate_key().decode()
                else:
                    new_value = secrets.token_urlsafe(32)
            
            # Update metadata
            metadata.last_rotated = datetime.now(timezone.utc)
            
            # Store rotated secret
            if self.use_azure and self.azure_manager:
                success = await self.azure_manager.rotate_secret(name, new_value)
            else:
                success = self.local_store.set_secret(name, new_value, metadata)
            
            if success:
                logger.info(f"Secret rotated successfully: {name}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error rotating secret {name}: {e}")
            return False
    
    async def check_rotation_schedule(self) -> List[str]:
        """Check which secrets need rotation"""
        secrets_to_rotate = []
        current_time = datetime.now(timezone.utc)
        
        for name, metadata in self.rotation_schedule.items():
            time_since_rotation = current_time - metadata.last_rotated
            if time_since_rotation >= metadata.rotation_interval:
                secrets_to_rotate.append(name)
        
        return secrets_to_rotate
    
    async def auto_rotate_secrets(self) -> Dict[str, bool]:
        """Automatically rotate secrets that are due"""
        secrets_to_rotate = await self.check_rotation_schedule()
        rotation_results = {}
        
        for secret_name in secrets_to_rotate:
            try:
                success = await self.rotate_secret(secret_name)
                rotation_results[secret_name] = success
                
                if success:
                    logger.info(f"Auto-rotated secret: {secret_name}")
                else:
                    logger.error(f"Failed to auto-rotate secret: {secret_name}")
                    
            except Exception as e:
                logger.error(f"Error during auto-rotation of {secret_name}: {e}")
                rotation_results[secret_name] = False
        
        return rotation_results
    
    def get_secret_sync(self, name: str) -> Optional[str]:
        """Synchronous version of get_secret for compatibility"""
        try:
            if self.use_azure and self.azure_manager:
                # For sync access, we'll use the local cache or environment fallback
                return os.getenv(name.upper().replace('-', '_'))
            else:
                return self.local_store.get_secret(name)
        except Exception as e:
            logger.error(f"Error retrieving secret synchronously {name}: {e}")
            return None

class DataProtectionManager:
    """Data protection and PII handling utilities"""
    
    def __init__(self, encryption_key: Optional[str] = None):
        # Initialize encryption
        if encryption_key:
            self.fernet = Fernet(encryption_key.encode())
        else:
            # Derive key from environment or generate
            key_material = os.getenv('DATA_PROTECTION_KEY', secrets.token_urlsafe(32))
            key = base64.urlsafe_b64encode(
                PBKDF2HMAC(
                    algorithm=hashes.SHA256(),
                    length=32,
                    salt=b'comicguess_salt',  # In production, use random salt per installation
                    iterations=100000,
                ).derive(key_material.encode())
            )
            self.fernet = Fernet(key)
        
        # PII field patterns
        self.pii_patterns = {
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'credit_card': r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
            'ip_address': r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'
        }
        
        # Data retention policies (in days)
        self.retention_policies = {
            'user_sessions': 30,
            'audit_logs': 365,
            'user_data': 2555,  # 7 years
            'temporary_data': 7,
            'analytics_data': 90
        }
    
    def encrypt_pii(self, data: str) -> str:
        """Encrypt personally identifiable information"""
        try:
            return self.fernet.encrypt(data.encode()).decode()
        except Exception as e:
            logger.error(f"Error encrypting PII: {e}")
            raise
    
    def decrypt_pii(self, encrypted_data: str) -> str:
        """Decrypt personally identifiable information"""
        try:
            return self.fernet.decrypt(encrypted_data.encode()).decode()
        except Exception as e:
            logger.error(f"Error decrypting PII: {e}")
            raise
    
    def hash_pii(self, data: str, salt: Optional[str] = None) -> str:
        """Create irreversible hash of PII for analytics"""
        if salt is None:
            salt = os.getenv('PII_HASH_SALT', 'default_salt')
        
        combined = f"{data}{salt}"
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def sanitize_logs(self, log_data: str) -> str:
        """Remove PII from log data"""
        import re
        
        sanitized = log_data
        
        for pii_type, pattern in self.pii_patterns.items():
            if pii_type == 'email':
                sanitized = re.sub(pattern, '[EMAIL_REDACTED]', sanitized)
            elif pii_type == 'phone':
                sanitized = re.sub(pattern, '[PHONE_REDACTED]', sanitized)
            elif pii_type == 'ssn':
                sanitized = re.sub(pattern, '[SSN_REDACTED]', sanitized)
            elif pii_type == 'credit_card':
                sanitized = re.sub(pattern, '[CARD_REDACTED]', sanitized)
            elif pii_type == 'ip_address':
                # Partially redact IP addresses (keep first two octets)
                sanitized = re.sub(r'(\d{1,3}\.\d{1,3})\.\d{1,3}\.\d{1,3}', r'\1.XXX.XXX', sanitized)
        
        return sanitized
    
    def should_purge_data(self, data_type: str, created_at: datetime) -> bool:
        """Check if data should be purged based on retention policy"""
        if data_type not in self.retention_policies:
            return False
        
        retention_days = self.retention_policies[data_type]
        age = datetime.now(timezone.utc) - created_at
        
        return age.days > retention_days
    
    def create_data_purge_plan(self, data_inventory: Dict[str, List[Dict]]) -> Dict[str, List[str]]:
        """Create a plan for purging expired data"""
        purge_plan = {}
        
        for data_type, records in data_inventory.items():
            records_to_purge = []
            
            for record in records:
                created_at = record.get('created_at')
                record_id = record.get('id')
                
                if created_at and record_id:
                    if isinstance(created_at, str):
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    
                    if self.should_purge_data(data_type, created_at):
                        records_to_purge.append(record_id)
            
            if records_to_purge:
                purge_plan[data_type] = records_to_purge
        
        return purge_plan
    
    def anonymize_user_data(self, user_data: Dict[str, Any]) -> Dict[str, Any]:
        """Anonymize user data for analytics while preserving utility"""
        anonymized = user_data.copy()
        
        # Replace identifiable fields with hashed versions
        if 'email' in anonymized:
            anonymized['email_hash'] = self.hash_pii(anonymized['email'])
            del anonymized['email']
        
        if 'username' in anonymized:
            anonymized['username_hash'] = self.hash_pii(anonymized['username'])
            del anonymized['username']
        
        if 'ip_address' in anonymized:
            # Keep only country/region level info
            anonymized['ip_hash'] = self.hash_pii(anonymized['ip_address'])
            del anonymized['ip_address']
        
        # Remove other PII fields
        pii_fields = ['phone', 'address', 'full_name', 'ssn', 'credit_card']
        for field in pii_fields:
            if field in anonymized:
                del anonymized[field]
        
        return anonymized

# Global instances
secrets_manager = SecretsManager()
data_protection = DataProtectionManager()

# Convenience functions
async def get_secret(name: str) -> Optional[str]:
    """Get a secret value"""
    return await secrets_manager.get_secret(name)

def get_secret_sync(name: str) -> Optional[str]:
    """Get a secret value synchronously"""
    return secrets_manager.get_secret_sync(name)

async def set_secret(name: str, value: str, secret_type: SecretType = SecretType.API_KEY) -> bool:
    """Set a secret value"""
    return await secrets_manager.set_secret(name, value, secret_type)

async def rotate_secret(name: str, new_value: Optional[str] = None) -> bool:
    """Rotate a secret"""
    return await secrets_manager.rotate_secret(name, new_value)

def encrypt_pii(data: str) -> str:
    """Encrypt PII data"""
    return data_protection.encrypt_pii(data)

def decrypt_pii(encrypted_data: str) -> str:
    """Decrypt PII data"""
    return data_protection.decrypt_pii(encrypted_data)

def sanitize_logs(log_data: str) -> str:
    """Sanitize log data"""
    return data_protection.sanitize_logs(log_data)