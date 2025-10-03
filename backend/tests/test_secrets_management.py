"""
Tests for secrets management and data protection
"""

import pytest
import os
import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock, AsyncMock

from app.security.secrets_manager import (
    SecretsManager, LocalSecretsStore, AzureKeyVaultManager,
    DataProtectionManager, SecretType, SecretMetadata
)
from app.security.data_lifecycle import (
    DataInventoryManager, DataRetentionManager, AccountDeletionManager,
    GDPRComplianceManager, DataCategory, PurgeReason, DataRecord
)


class TestLocalSecretsStore:
    """Test local secrets storage functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.store = LocalSecretsStore()
    
    def test_set_and_get_secret(self):
        """Test storing and retrieving secrets"""
        secret_name = "test_secret"
        secret_value = "super_secret_value"
        
        # Store secret
        success = self.store.set_secret(secret_name, secret_value)
        assert success is True
        
        # Retrieve secret
        retrieved_value = self.store.get_secret(secret_name)
        assert retrieved_value == secret_value
    
    def test_secret_encryption(self):
        """Test that secrets are encrypted in storage"""
        secret_name = "test_secret"
        secret_value = "super_secret_value"
        
        # Store secret
        self.store.set_secret(secret_name, secret_value)
        
        # Check that stored value is encrypted (different from original)
        stored_value = self.store.secrets[secret_name]
        assert stored_value != secret_value
        assert len(stored_value) > len(secret_value)  # Encrypted data is longer
    
    def test_delete_secret(self):
        """Test secret deletion"""
        secret_name = "test_secret"
        secret_value = "super_secret_value"
        
        # Store and verify secret exists
        self.store.set_secret(secret_name, secret_value)
        assert self.store.get_secret(secret_name) == secret_value
        
        # Delete secret
        success = self.store.delete_secret(secret_name)
        assert success is True
        
        # Verify secret is gone
        assert self.store.get_secret(secret_name) is None
    
    def test_list_secrets(self):
        """Test listing secret names"""
        secrets = {
            "secret1": "value1",
            "secret2": "value2",
            "secret3": "value3"
        }
        
        # Store multiple secrets
        for name, value in secrets.items():
            self.store.set_secret(name, value)
        
        # List secrets
        secret_names = self.store.list_secrets()
        assert set(secret_names) == set(secrets.keys())
    
    def test_metadata_storage(self):
        """Test storing secrets with metadata"""
        secret_name = "test_secret"
        secret_value = "super_secret_value"
        
        metadata = SecretMetadata(
            name=secret_name,
            secret_type=SecretType.API_KEY,
            created_at=datetime.now(timezone.utc),
            last_rotated=datetime.now(timezone.utc),
            rotation_interval=timedelta(days=90)
        )
        
        # Store secret with metadata
        success = self.store.set_secret(secret_name, secret_value, metadata)
        assert success is True
        
        # Verify metadata is stored
        assert secret_name in self.store.metadata
        stored_metadata = self.store.metadata[secret_name]
        assert stored_metadata.secret_type == SecretType.API_KEY
        assert stored_metadata.rotation_interval == timedelta(days=90)


class TestAzureKeyVaultManager:
    """Test Azure Key Vault integration"""
    
    def setup_method(self):
        """Setup test environment"""
        # Mock Azure SDK components
        self.mock_client = Mock()
        self.mock_credential = Mock()
        
        with patch('app.security.secrets_manager.AZURE_AVAILABLE', True):
            with patch('app.security.secrets_manager.SecretClient') as mock_secret_client:
                with patch('app.security.secrets_manager.DefaultAzureCredential') as mock_cred:
                    mock_secret_client.return_value = self.mock_client
                    mock_cred.return_value = self.mock_credential
                    
                    self.manager = AzureKeyVaultManager("https://test-vault.vault.azure.net/")
    
    @pytest.mark.asyncio
    async def test_set_secret_with_metadata(self):
        """Test storing secret in Azure Key Vault with metadata"""
        secret_name = "test_secret"
        secret_value = "super_secret_value"
        
        metadata = SecretMetadata(
            name=secret_name,
            secret_type=SecretType.JWT_SECRET,
            created_at=datetime.now(timezone.utc),
            last_rotated=datetime.now(timezone.utc),
            rotation_interval=timedelta(days=30)
        )
        
        # Mock successful response
        mock_secret = Mock()
        mock_secret.name = secret_name
        self.mock_client.set_secret.return_value = mock_secret
        
        # Store secret
        success = await self.manager.set_secret(secret_name, secret_value, metadata)
        assert success is True
        
        # Verify client was called with correct parameters
        self.mock_client.set_secret.assert_called_once()
        call_args = self.mock_client.set_secret.call_args
        assert call_args[0][0] == secret_name
        assert call_args[0][1] == secret_value
        
        # Check tags were set correctly
        tags = call_args[1]['tags']
        assert tags['secret_type'] == SecretType.JWT_SECRET.value
        assert 'created_at' in tags
        assert 'rotation_interval_days' in tags
    
    @pytest.mark.asyncio
    async def test_get_secret(self):
        """Test retrieving secret from Azure Key Vault"""
        secret_name = "test_secret"
        secret_value = "super_secret_value"
        
        # Mock successful response
        mock_secret = Mock()
        mock_secret.value = secret_value
        self.mock_client.get_secret.return_value = mock_secret
        
        # Retrieve secret
        retrieved_value = await self.manager.get_secret(secret_name)
        assert retrieved_value == secret_value
        
        # Verify client was called
        self.mock_client.get_secret.assert_called_once_with(secret_name)
    
    @pytest.mark.asyncio
    async def test_get_secret_not_found(self):
        """Test handling of secret not found"""
        secret_name = "nonexistent_secret"
        
        # Mock ResourceNotFoundError
        from app.security.secrets_manager import ResourceNotFoundError
        self.mock_client.get_secret.side_effect = ResourceNotFoundError("Secret not found")
        
        # Retrieve secret
        retrieved_value = await self.manager.get_secret(secret_name)
        assert retrieved_value is None
    
    @pytest.mark.asyncio
    async def test_delete_secret(self):
        """Test deleting secret from Azure Key Vault"""
        secret_name = "test_secret"
        
        # Mock successful deletion
        mock_operation = Mock()
        mock_operation.wait.return_value = None
        self.mock_client.begin_delete_secret.return_value = mock_operation
        
        # Delete secret
        success = await self.manager.delete_secret(secret_name)
        assert success is True
        
        # Verify client was called
        self.mock_client.begin_delete_secret.assert_called_once_with(secret_name)
    
    @pytest.mark.asyncio
    async def test_list_secrets(self):
        """Test listing secrets from Azure Key Vault"""
        secret_names = ["secret1", "secret2", "secret3"]
        
        # Mock secret properties
        mock_properties = []
        for name in secret_names:
            prop = Mock()
            prop.name = name
            mock_properties.append(prop)
        
        self.mock_client.list_properties_of_secrets.return_value = mock_properties
        
        # List secrets
        retrieved_names = await self.manager.list_secrets()
        assert set(retrieved_names) == set(secret_names)
    
    @pytest.mark.asyncio
    async def test_rotate_secret(self):
        """Test secret rotation"""
        secret_name = "test_secret"
        old_value = "old_secret_value"
        new_value = "new_secret_value"
        
        # Setup metadata in cache
        metadata = SecretMetadata(
            name=secret_name,
            secret_type=SecretType.API_KEY,
            created_at=datetime.now(timezone.utc) - timedelta(days=30),
            last_rotated=datetime.now(timezone.utc) - timedelta(days=30),
            rotation_interval=timedelta(days=30)
        )
        self.manager.metadata_cache[secret_name] = metadata
        
        # Mock successful rotation
        mock_secret = Mock()
        mock_secret.name = secret_name
        self.mock_client.set_secret.return_value = mock_secret
        
        # Rotate secret
        success = await self.manager.rotate_secret(secret_name, new_value)
        assert success is True
        
        # Verify metadata was updated
        updated_metadata = self.manager.metadata_cache[secret_name]
        assert updated_metadata.last_rotated > metadata.last_rotated


class TestSecretsManager:
    """Test unified secrets manager"""
    
    def setup_method(self):
        """Setup test environment"""
        # Mock environment to use local store
        with patch.dict(os.environ, {}, clear=True):
            self.manager = SecretsManager()
    
    @pytest.mark.asyncio
    async def test_set_and_get_secret(self):
        """Test setting and getting secrets"""
        secret_name = "test_api_key"
        secret_value = "sk_test_123456789"
        
        # Set secret
        success = await self.manager.set_secret(
            secret_name, 
            secret_value, 
            SecretType.API_KEY
        )
        assert success is True
        
        # Get secret
        retrieved_value = await self.manager.get_secret(secret_name)
        assert retrieved_value == secret_value
    
    @pytest.mark.asyncio
    async def test_secret_rotation_scheduling(self):
        """Test secret rotation scheduling"""
        secret_name = "test_jwt_secret"
        secret_value = "jwt_secret_123"
        
        # Set secret with short rotation interval
        success = await self.manager.set_secret(
            secret_name,
            secret_value,
            SecretType.JWT_SECRET,
            rotation_interval=timedelta(seconds=1)
        )
        assert success is True
        
        # Check rotation schedule
        assert secret_name in self.manager.rotation_schedule
        
        # Wait for rotation to be due
        await asyncio.sleep(2)
        
        # Check which secrets need rotation
        secrets_to_rotate = await self.manager.check_rotation_schedule()
        assert secret_name in secrets_to_rotate
    
    @pytest.mark.asyncio
    async def test_auto_rotate_secrets(self):
        """Test automatic secret rotation"""
        secret_name = "test_auto_rotate"
        secret_value = "original_value"
        
        # Set secret with immediate rotation
        await self.manager.set_secret(
            secret_name,
            secret_value,
            SecretType.API_KEY,
            rotation_interval=timedelta(seconds=0)
        )
        
        # Perform auto-rotation
        rotation_results = await self.manager.auto_rotate_secrets()
        
        # Verify rotation occurred
        assert secret_name in rotation_results
        assert rotation_results[secret_name] is True
        
        # Verify secret value changed
        new_value = await self.manager.get_secret(secret_name)
        assert new_value != secret_value
        assert new_value is not None
    
    @pytest.mark.asyncio
    async def test_delete_secret(self):
        """Test secret deletion"""
        secret_name = "test_delete"
        secret_value = "delete_me"
        
        # Set secret
        await self.manager.set_secret(secret_name, secret_value)
        assert await self.manager.get_secret(secret_name) == secret_value
        
        # Delete secret
        success = await self.manager.delete_secret(secret_name)
        assert success is True
        
        # Verify secret is gone
        assert await self.manager.get_secret(secret_name) is None
        assert secret_name not in self.manager.rotation_schedule
    
    def test_get_secret_sync(self):
        """Test synchronous secret retrieval"""
        secret_name = "test_sync"
        secret_value = "sync_value"
        
        # Store secret in local store
        self.manager.local_store.set_secret(secret_name, secret_value)
        
        # Retrieve synchronously
        retrieved_value = self.manager.get_secret_sync(secret_name)
        assert retrieved_value == secret_value


class TestDataProtectionManager:
    """Test data protection and PII handling"""
    
    def setup_method(self):
        """Setup test environment"""
        self.data_protection = DataProtectionManager()
    
    def test_encrypt_decrypt_pii(self):
        """Test PII encryption and decryption"""
        pii_data = "user@example.com"
        
        # Encrypt PII
        encrypted_data = self.data_protection.encrypt_pii(pii_data)
        assert encrypted_data != pii_data
        assert len(encrypted_data) > len(pii_data)
        
        # Decrypt PII
        decrypted_data = self.data_protection.decrypt_pii(encrypted_data)
        assert decrypted_data == pii_data
    
    def test_hash_pii(self):
        """Test PII hashing for analytics"""
        pii_data = "user@example.com"
        
        # Hash PII
        hash1 = self.data_protection.hash_pii(pii_data)
        hash2 = self.data_protection.hash_pii(pii_data)
        
        # Hashes should be consistent
        assert hash1 == hash2
        assert hash1 != pii_data
        assert len(hash1) == 64  # SHA256 hex length
        
        # Different data should produce different hashes
        hash3 = self.data_protection.hash_pii("different@example.com")
        assert hash3 != hash1
    
    def test_sanitize_logs(self):
        """Test log sanitization"""
        log_data = """
        User login: user@example.com from IP 192.168.1.100
        Phone number: 555-123-4567
        Credit card: 4111-1111-1111-1111
        SSN: 123-45-6789
        """
        
        sanitized = self.data_protection.sanitize_logs(log_data)
        
        # Check that PII is redacted
        assert "user@example.com" not in sanitized
        assert "[EMAIL_REDACTED]" in sanitized
        assert "555-123-4567" not in sanitized
        assert "[PHONE_REDACTED]" in sanitized
        assert "4111-1111-1111-1111" not in sanitized
        assert "[CARD_REDACTED]" in sanitized
        assert "123-45-6789" not in sanitized
        assert "[SSN_REDACTED]" in sanitized
        
        # IP should be partially redacted
        assert "192.168.1.100" not in sanitized
        assert "192.168.XXX.XXX" in sanitized
    
    def test_retention_policy_check(self):
        """Test data retention policy checking"""
        # Test data that should be purged
        old_date = datetime.now(timezone.utc) - timedelta(days=400)
        assert self.data_protection.should_purge_data("analytics_data", old_date) is True
        
        # Test data that should be kept
        recent_date = datetime.now(timezone.utc) - timedelta(days=30)
        assert self.data_protection.should_purge_data("analytics_data", recent_date) is False
        
        # Test unknown data type (should not purge)
        assert self.data_protection.should_purge_data("unknown_type", old_date) is False
    
    def test_create_data_purge_plan(self):
        """Test data purge plan creation"""
        current_time = datetime.now(timezone.utc)
        
        data_inventory = {
            "analytics_data": [
                {
                    "id": "record1",
                    "created_at": (current_time - timedelta(days=100)).isoformat()
                },
                {
                    "id": "record2", 
                    "created_at": (current_time - timedelta(days=30)).isoformat()
                }
            ],
            "user_data": [
                {
                    "id": "user1",
                    "created_at": (current_time - timedelta(days=3000)).isoformat()
                }
            ]
        }
        
        purge_plan = self.data_protection.create_data_purge_plan(data_inventory)
        
        # Analytics data record1 should be purged (>90 days)
        assert "analytics_data" in purge_plan
        assert "record1" in purge_plan["analytics_data"]
        assert "record2" not in purge_plan["analytics_data"]
        
        # User data should not be purged (retention is 7 years)
        assert "user_data" not in purge_plan
    
    def test_anonymize_user_data(self):
        """Test user data anonymization"""
        user_data = {
            "id": "user123",
            "email": "user@example.com",
            "username": "testuser",
            "ip_address": "192.168.1.100",
            "phone": "555-123-4567",
            "game_stats": {"total_games": 50, "wins": 30},
            "preferences": {"theme": "dark"}
        }
        
        anonymized = self.data_protection.anonymize_user_data(user_data)
        
        # Check that PII is removed/hashed
        assert "email" not in anonymized
        assert "email_hash" in anonymized
        assert "username" not in anonymized
        assert "username_hash" in anonymized
        assert "ip_address" not in anonymized
        assert "ip_hash" in anonymized
        assert "phone" not in anonymized
        
        # Check that non-PII data is preserved
        assert anonymized["id"] == "user123"
        assert anonymized["game_stats"] == {"total_games": 50, "wins": 30}
        assert anonymized["preferences"] == {"theme": "dark"}


class TestDataInventoryManager:
    """Test data inventory management"""
    
    def setup_method(self):
        """Setup test environment"""
        self.inventory_manager = DataInventoryManager()
    
    @pytest.mark.asyncio
    async def test_get_user_data_inventory(self):
        """Test getting user data inventory"""
        user_id = "test_user_123"
        
        # Mock repositories
        with patch.object(self.inventory_manager, 'user_repo') as mock_user_repo:
            with patch.object(self.inventory_manager, 'guess_repo') as mock_guess_repo:
                # Mock user data
                mock_user = Mock()
                mock_user.id = user_id
                mock_user.email = "test@example.com"
                mock_user.created_at = datetime.now(timezone.utc)
                mock_user.to_dict.return_value = {"id": user_id, "email": "test@example.com"}
                mock_user_repo.get_user_by_id.return_value = mock_user
                
                # Mock guesses
                mock_guess = Mock()
                mock_guess.id = "guess123"
                mock_guess.puzzle_id = "puzzle123"
                mock_guess.timestamp = datetime.now(timezone.utc)
                mock_guess.to_dict.return_value = {"id": "guess123", "puzzle_id": "puzzle123"}
                mock_guess_repo.get_user_guesses.return_value = [mock_guess]
                
                # Mock stats
                mock_user_repo.get_user_stats.return_value = {"total_games": 10, "wins": 5}
                
                # Get inventory
                inventory = await self.inventory_manager.get_user_data_inventory(user_id)
                
                # Verify inventory structure
                assert DataCategory.PERSONAL_DATA in inventory
                assert DataCategory.USAGE_DATA in inventory
                assert DataCategory.ANALYTICS_DATA in inventory
                
                # Check personal data
                personal_records = inventory[DataCategory.PERSONAL_DATA]
                assert len(personal_records) == 1
                assert personal_records[0].user_id == user_id
                assert personal_records[0].contains_pii is True
                
                # Check usage data
                usage_records = inventory[DataCategory.USAGE_DATA]
                assert len(usage_records) == 1
                assert usage_records[0].contains_pii is False


class TestAccountDeletionManager:
    """Test account deletion functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.deletion_manager = AccountDeletionManager()
    
    @pytest.mark.asyncio
    async def test_delete_user_account(self):
        """Test complete user account deletion"""
        user_id = "test_user_delete"
        
        # Mock dependencies
        with patch.object(self.deletion_manager, 'inventory_manager') as mock_inventory:
            with patch.object(self.deletion_manager, 'user_repo') as mock_user_repo:
                with patch.object(self.deletion_manager, 'guess_repo') as mock_guess_repo:
                    with patch('app.security.data_lifecycle.revoke_all_user_tokens') as mock_revoke:
                        with patch('app.security.data_lifecycle.session_manager') as mock_session:
                            
                            # Mock inventory
                            mock_inventory.get_user_data_inventory.return_value = {
                                DataCategory.PERSONAL_DATA: [Mock()],
                                DataCategory.USAGE_DATA: [Mock(), Mock()]
                            }
                            
                            # Mock repository operations
                            mock_guess_repo.delete_user_guesses.return_value = 5
                            mock_user_repo.delete_user.return_value = True
                            
                            # Perform deletion
                            operation = await self.deletion_manager.delete_user_account(user_id)
                            
                            # Verify operation
                            assert operation.user_id == user_id
                            assert operation.reason == PurgeReason.ACCOUNT_DELETION
                            assert operation.records_count == 3  # 1 personal + 2 usage
                            assert operation.completed_at is not None
                            
                            # Verify all cleanup operations were called
                            mock_revoke.assert_called_once_with(user_id)
                            mock_session.invalidate_all_sessions.assert_called_once_with(user_id)
                            mock_guess_repo.delete_user_guesses.assert_called_once_with(user_id)
                            mock_user_repo.delete_user.assert_called_once_with(user_id)
    
    @pytest.mark.asyncio
    async def test_export_user_data(self):
        """Test user data export for GDPR"""
        user_id = "test_user_export"
        
        # Mock dependencies
        with patch.object(self.deletion_manager, 'inventory_manager') as mock_inventory:
            with patch.object(self.deletion_manager, 'user_repo') as mock_user_repo:
                with patch.object(self.deletion_manager, 'guess_repo') as mock_guess_repo:
                    
                    # Mock user data
                    mock_user = Mock()
                    mock_user.to_dict.return_value = {"id": user_id, "email": "test@example.com"}
                    mock_user_repo.get_user_by_id.return_value = mock_user
                    
                    # Mock guesses
                    mock_guess = Mock()
                    mock_guess.to_dict.return_value = {"id": "guess123", "puzzle_id": "puzzle123"}
                    mock_guess_repo.get_user_guesses.return_value = [mock_guess]
                    
                    # Mock stats
                    mock_user_repo.get_user_stats.return_value = {"total_games": 10}
                    
                    # Mock inventory with proper metadata
                    personal_record = Mock()
                    personal_record.metadata = {"type": "user_profile"}
                    
                    usage_record = Mock()
                    usage_record.metadata = {"type": "guess"}
                    
                    stats_record = Mock()
                    stats_record.metadata = {"type": "user_stats"}
                    
                    mock_inventory.get_user_data_inventory.return_value = {
                        DataCategory.PERSONAL_DATA: [personal_record],
                        DataCategory.USAGE_DATA: [usage_record],
                        DataCategory.ANALYTICS_DATA: [stats_record]
                    }
                    
                    # Export data
                    export_data = await self.deletion_manager.export_user_data(user_id)
                    
                    # Verify export structure
                    assert "export_generated_at" in export_data
                    assert export_data["user_id"] == user_id
                    assert "data_categories" in export_data
                    
                    # Check that data categories are present
                    categories = export_data["data_categories"]
                    assert DataCategory.PERSONAL_DATA.value in categories
                    assert DataCategory.USAGE_DATA.value in categories
                    assert DataCategory.ANALYTICS_DATA.value in categories


class TestGDPRComplianceManager:
    """Test GDPR compliance functionality"""
    
    def setup_method(self):
        """Setup test environment"""
        self.gdpr_manager = GDPRComplianceManager()
    
    @pytest.mark.asyncio
    async def test_handle_access_request(self):
        """Test GDPR access request handling"""
        user_id = "test_user_access"
        
        with patch.object(self.gdpr_manager.account_deletion, 'export_user_data') as mock_export:
            mock_export.return_value = {"user_id": user_id, "data": "exported_data"}
            
            result = await self.gdpr_manager.handle_data_subject_request(user_id, "access")
            
            assert result["user_id"] == user_id
            mock_export.assert_called_once_with(user_id)
    
    @pytest.mark.asyncio
    async def test_handle_deletion_request(self):
        """Test GDPR deletion request handling"""
        user_id = "test_user_deletion"
        
        with patch.object(self.gdpr_manager.account_deletion, 'delete_user_account') as mock_delete:
            mock_operation = Mock()
            mock_operation.operation_id = "op123"
            mock_operation.success = True
            mock_operation.completed_at = datetime.now(timezone.utc)
            mock_operation.errors = []
            mock_delete.return_value = mock_operation
            
            result = await self.gdpr_manager.handle_data_subject_request(user_id, "deletion")
            
            assert result["operation_id"] == "op123"
            assert result["success"] is True
            mock_delete.assert_called_once_with(user_id, "gdpr_request")
    
    @pytest.mark.asyncio
    async def test_generate_compliance_report(self):
        """Test GDPR compliance report generation"""
        with patch.object(self.gdpr_manager.retention_manager, 'create_retention_report') as mock_report:
            mock_report.return_value = {
                "total_expired_records": 0,
                "expired_data_summary": {}
            }
            
            report = await self.gdpr_manager.generate_compliance_report()
            
            assert "generated_at" in report
            assert "gdpr_compliance_status" in report
            assert "data_retention" in report
            assert "recommendations" in report
            assert "action_items" in report
            
            # Should be compliant with no expired records
            assert report["gdpr_compliance_status"] == "compliant"


@pytest.mark.integration
class TestSecretsManagementIntegration:
    """Integration tests for secrets management"""
    
    @pytest.mark.asyncio
    async def test_complete_secret_lifecycle(self):
        """Test complete secret lifecycle"""
        # Use local secrets manager for integration test
        with patch.dict(os.environ, {}, clear=True):
            manager = SecretsManager()
        
        secret_name = "integration_test_secret"
        secret_value = "initial_secret_value"
        
        # 1. Set secret
        success = await manager.set_secret(
            secret_name,
            secret_value,
            SecretType.API_KEY,
            rotation_interval=timedelta(seconds=1)
        )
        assert success is True
        
        # 2. Get secret
        retrieved_value = await manager.get_secret(secret_name)
        assert retrieved_value == secret_value
        
        # 3. Wait for rotation to be due
        await asyncio.sleep(2)
        
        # 4. Check rotation schedule
        secrets_to_rotate = await manager.check_rotation_schedule()
        assert secret_name in secrets_to_rotate
        
        # 5. Rotate secret
        rotation_success = await manager.rotate_secret(secret_name)
        assert rotation_success is True
        
        # 6. Verify new value is different
        new_value = await manager.get_secret(secret_name)
        assert new_value != secret_value
        assert new_value is not None
        
        # 7. Delete secret
        delete_success = await manager.delete_secret(secret_name)
        assert delete_success is True
        
        # 8. Verify secret is gone
        final_value = await manager.get_secret(secret_name)
        assert final_value is None
    
    @pytest.mark.asyncio
    async def test_data_protection_workflow(self):
        """Test complete data protection workflow"""
        data_protection = DataProtectionManager()
        
        # Test PII handling
        original_email = "user@example.com"
        
        # Encrypt PII
        encrypted_email = data_protection.encrypt_pii(original_email)
        assert encrypted_email != original_email
        
        # Decrypt PII
        decrypted_email = data_protection.decrypt_pii(encrypted_email)
        assert decrypted_email == original_email
        
        # Hash for analytics
        email_hash = data_protection.hash_pii(original_email)
        assert email_hash != original_email
        assert len(email_hash) == 64
        
        # Test log sanitization
        log_with_pii = f"User {original_email} logged in from 192.168.1.100"
        sanitized_log = data_protection.sanitize_logs(log_with_pii)
        assert original_email not in sanitized_log
        assert "[EMAIL_REDACTED]" in sanitized_log
        assert "192.168.XXX.XXX" in sanitized_log