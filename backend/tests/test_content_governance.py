"""Tests for content governance functionality"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from app.models.content_governance import (
    CanonicalCharacter,
    DuplicateDetection,
    ContentReviewRequest,
    LocaleAwareNameMatcher,
    ContentGovernanceReport,
    ContentStatus,
    ContentType,
    DuplicateType
)
from app.services.content_governance_service import ContentGovernanceService


class TestCanonicalCharacter:
    """Test canonical character model"""
    
    def test_create_canonical_character(self):
        """Test creating a canonical character"""
        character = CanonicalCharacter(
            canonical_name="Spider-Man",
            universe="marvel",
            approved_aliases=["Spidey", "Web-Slinger"],
            created_by="admin-123"
        )
        
        assert character.canonical_name == "Spider-Man"
        assert character.universe == "marvel"
        assert len(character.approved_aliases) == 2
        assert "Spidey" in character.approved_aliases
    
    def test_add_alias(self):
        """Test adding an alias to a character"""
        character = CanonicalCharacter(
            canonical_name="Batman",
            universe="dc",
            created_by="admin-123"
        )
        
        # Add new alias
        success = character.add_alias("Dark Knight")
        assert success is True
        assert "Dark Knight" in character.approved_aliases
        
        # Try to add duplicate alias
        success = character.add_alias("Dark Knight")
        assert success is False
        assert character.approved_aliases.count("Dark Knight") == 1
    
    def test_reject_alias(self):
        """Test rejecting an alias"""
        character = CanonicalCharacter(
            canonical_name="Superman",
            universe="dc",
            approved_aliases=["Man of Steel", "Last Son of Krypton"],
            created_by="admin-123"
        )
        
        # Reject existing alias
        success = character.reject_alias("Man of Steel")
        assert success is True
        assert "Man of Steel" not in character.approved_aliases
        assert "Man of Steel" in character.rejected_aliases
        
        # Reject new alias
        success = character.reject_alias("Blue Boy Scout")
        assert success is True
        assert "Blue Boy Scout" in character.rejected_aliases
    
    def test_get_all_names(self):
        """Test getting all valid names for a character"""
        character = CanonicalCharacter(
            canonical_name="Wonder Woman",
            universe="dc",
            approved_aliases=["Diana Prince", "Amazon Princess"],
            created_by="admin-123"
        )
        
        all_names = character.get_all_names()
        assert len(all_names) == 3
        assert "Wonder Woman" in all_names
        assert "Diana Prince" in all_names
        assert "Amazon Princess" in all_names
    
    def test_canonical_name_validation(self):
        """Test canonical name validation"""
        with pytest.raises(ValueError, match="Canonical name cannot be empty"):
            CanonicalCharacter(
                canonical_name="",
                universe="marvel",
                created_by="admin-123"
            )
        
        with pytest.raises(ValueError, match="must be at least 2 characters"):
            CanonicalCharacter(
                canonical_name="X",
                universe="marvel",
                created_by="admin-123"
            )


class TestLocaleAwareNameMatcher:
    """Test locale-aware name matching"""
    
    def test_normalize_name(self):
        """Test name normalization"""
        matcher = LocaleAwareNameMatcher()
        
        # Basic normalization
        assert matcher.normalize_name("Spider-Man") == "spider-man"
        assert matcher.normalize_name("  BATMAN  ") == "batman"
        
        # Prefix removal
        assert matcher.normalize_name("The Flash") == "flash"
        assert matcher.normalize_name("Dr. Strange") == "strange"
        assert matcher.normalize_name("Captain America") == "america"
        
        # Suffix removal
        assert matcher.normalize_name("Tony Stark Jr.") == "tony stark"
        assert matcher.normalize_name("Reed Richards II") == "reed richards"
        
        # Special character removal
        assert matcher.normalize_name("Spider-Man!") == "spider-man"
        assert matcher.normalize_name("X-Men (Team)") == "x-men team"
    
    def test_calculate_similarity(self):
        """Test similarity calculation"""
        matcher = LocaleAwareNameMatcher()
        
        # Exact match
        assert matcher.calculate_similarity("Spider-Man", "Spider-Man") == 1.0
        
        # Case insensitive
        assert matcher.calculate_similarity("batman", "BATMAN") == 1.0
        
        # High similarity
        similarity = matcher.calculate_similarity("Spider-Man", "Spiderman")
        assert similarity > 0.8
        
        # Low similarity
        similarity = matcher.calculate_similarity("Batman", "Superman")
        assert similarity < 0.5
        
        # Empty strings
        assert matcher.calculate_similarity("", "") == 1.0
        assert matcher.calculate_similarity("Batman", "") == 0.0
    
    def test_is_phonetic_match(self):
        """Test phonetic matching"""
        matcher = LocaleAwareNameMatcher()
        
        # Should match phonetically similar names
        assert matcher.is_phonetic_match("Clark Kent", "Clerk Kent") is True
        assert matcher.is_phonetic_match("Peter Parker", "Petr Prkr") is True
        
        # Should not match very different names
        assert matcher.is_phonetic_match("Batman", "Superman") is False
        
        # Short names should not match phonetically
        assert matcher.is_phonetic_match("X", "Y") is False
    
    def test_find_potential_duplicates(self):
        """Test finding potential duplicates"""
        matcher = LocaleAwareNameMatcher()
        
        existing_names = [
            "Spider-Man",
            "Batman",
            "Superman",
            "Wonder Woman",
            "The Flash"
        ]
        
        # Find duplicates for exact match
        duplicates = matcher.find_potential_duplicates("Spider-Man", existing_names)
        assert len(duplicates) == 1
        assert duplicates[0]["name"] == "Spider-Man"
        assert duplicates[0]["type"] == DuplicateType.EXACT_MATCH
        
        # Find duplicates for similar name
        duplicates = matcher.find_potential_duplicates("Spiderman", existing_names)
        assert len(duplicates) >= 1
        spider_match = next((d for d in duplicates if d["name"] == "Spider-Man"), None)
        assert spider_match is not None
        assert spider_match["similarity"] > 0.8
        
        # Find no duplicates for unique name
        duplicates = matcher.find_potential_duplicates("Iron Man", existing_names, similarity_threshold=0.9)
        assert len(duplicates) == 0


class TestContentReviewRequest:
    """Test content review request model"""
    
    def test_create_review_request(self):
        """Test creating a content review request"""
        review = ContentReviewRequest(
            content_type=ContentType.CHARACTER,
            content_data={"canonical_name": "Iron Man", "universe": "marvel"},
            submitted_by="user-123"
        )
        
        assert review.content_type == ContentType.CHARACTER
        assert review.status == ContentStatus.PENDING
        assert review.submitted_by == "user-123"
        assert len(review.approvals) == 0
        assert len(review.rejections) == 0
    
    def test_add_approval(self):
        """Test adding approval to review request"""
        review = ContentReviewRequest(
            content_type=ContentType.CHARACTER,
            content_data={"canonical_name": "Iron Man", "universe": "marvel"},
            submitted_by="user-123",
            approval_threshold=2
        )
        
        # First approval
        success = review.add_approval("admin-1")
        assert success is True
        assert "admin-1" in review.approvals
        assert review.status == ContentStatus.PENDING  # Not enough approvals yet
        
        # Second approval - should approve
        success = review.add_approval("admin-2")
        assert success is True
        assert "admin-2" in review.approvals
        assert review.status == ContentStatus.APPROVED
        assert review.reviewed_at is not None
        
        # Try to add approval from same admin
        success = review.add_approval("admin-1")
        assert success is False
    
    def test_add_rejection(self):
        """Test adding rejection to review request"""
        review = ContentReviewRequest(
            content_type=ContentType.CHARACTER,
            content_data={"canonical_name": "Iron Man", "universe": "marvel"},
            submitted_by="user-123"
        )
        
        success = review.add_rejection("admin-1", "Duplicate character")
        assert success is True
        assert "admin-1" in review.rejections
        assert review.status == ContentStatus.REJECTED
        assert review.review_notes == "Duplicate character"
        assert review.reviewed_at is not None
    
    def test_approval_rejection_conflict(self):
        """Test that admin can't both approve and reject"""
        review = ContentReviewRequest(
            content_type=ContentType.CHARACTER,
            content_data={"canonical_name": "Iron Man", "universe": "marvel"},
            submitted_by="user-123"
        )
        
        # Admin approves first
        review.add_approval("admin-1")
        
        # Same admin tries to reject - should fail
        success = review.add_rejection("admin-1", "Changed mind")
        assert success is False
        assert "admin-1" not in review.rejections
        assert review.status == ContentStatus.PENDING


class TestContentGovernanceService:
    """Test content governance service"""
    
    @pytest.fixture
    def mock_governance_repo(self):
        """Mock governance repository"""
        return Mock()
    
    @pytest.fixture
    def mock_puzzle_repo(self):
        """Mock puzzle repository"""
        return Mock()
    
    @pytest.fixture
    def governance_service(self, mock_governance_repo, mock_puzzle_repo):
        """Create governance service with mocked dependencies"""
        service = ContentGovernanceService()
        service.governance_repo = mock_governance_repo
        service.puzzle_repo = mock_puzzle_repo
        return service
    
    @pytest.mark.asyncio
    async def test_create_canonical_character(self, governance_service, mock_governance_repo):
        """Test creating canonical character"""
        mock_governance_repo.get_canonical_characters_by_universe.return_value = []
        mock_governance_repo.create_canonical_character.return_value = CanonicalCharacter(
            canonical_name="Iron Man",
            universe="marvel",
            created_by="admin-123"
        )
        
        character = await governance_service.create_canonical_character(
            canonical_name="Iron Man",
            universe="marvel",
            approved_aliases=["Tony Stark"],
            created_by="admin-123"
        )
        
        assert character.canonical_name == "Iron Man"
        assert character.universe == "marvel"
        mock_governance_repo.create_canonical_character.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_detect_character_duplicates(self, governance_service, mock_governance_repo):
        """Test duplicate detection"""
        # Mock existing characters
        existing_character = CanonicalCharacter(
            canonical_name="Spider-Man",
            universe="marvel",
            approved_aliases=["Spidey"],
            created_by="admin-123"
        )
        mock_governance_repo.get_canonical_characters_by_universe.return_value = [existing_character]
        mock_governance_repo.create_duplicate_detection.return_value = None
        
        duplicates = await governance_service.detect_character_duplicates("Spiderman", "marvel")
        
        assert len(duplicates) >= 1
        spider_duplicate = next((d for d in duplicates if "Spider-Man" in d.existing_character_name), None)
        assert spider_duplicate is not None
        assert spider_duplicate.confidence_score > 0.8
    
    @pytest.mark.asyncio
    async def test_validate_character_name(self, governance_service, mock_governance_repo):
        """Test character name validation"""
        mock_governance_repo.get_canonical_characters_by_universe.return_value = []
        mock_governance_repo.create_duplicate_detection.return_value = None
        
        # Valid name
        result = await governance_service.validate_character_name("Iron Man", "marvel")
        assert result["is_valid"] is True
        assert len(result["issues"]) == 0
        
        # Invalid name (too short)
        result = await governance_service.validate_character_name("X", "marvel")
        assert result["is_valid"] is False
        assert any(issue["type"] == "invalid_format" for issue in result["issues"])
    
    @pytest.mark.asyncio
    async def test_add_character_alias(self, governance_service, mock_governance_repo):
        """Test adding character alias"""
        character = CanonicalCharacter(
            canonical_name="Batman",
            universe="dc",
            created_by="admin-123"
        )
        
        mock_governance_repo.get_canonical_character.return_value = character
        mock_governance_repo.get_canonical_characters_by_universe.return_value = [character]
        mock_governance_repo.update_canonical_character.return_value = character
        
        success = await governance_service.add_character_alias("char-123", "Dark Knight", "admin-456")
        
        assert success is True
        assert "Dark Knight" in character.approved_aliases
        mock_governance_repo.update_canonical_character.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_alias_conflicts(self, governance_service, mock_governance_repo):
        """Test checking for alias conflicts"""
        existing_character = CanonicalCharacter(
            canonical_name="Batman",
            universe="dc",
            approved_aliases=["Dark Knight"],
            created_by="admin-123"
        )
        
        mock_governance_repo.get_canonical_characters_by_universe.return_value = [existing_character]
        
        # Check for conflict with existing alias
        conflicts = await governance_service.check_alias_conflicts("Dark Knight", "dc")
        assert len(conflicts) == 1
        assert conflicts[0]["conflicting_name"] == "Dark Knight"
        
        # Check for no conflict with unique alias
        conflicts = await governance_service.check_alias_conflicts("Caped Crusader", "dc")
        assert len(conflicts) == 0
    
    @pytest.mark.asyncio
    async def test_create_content_review_request(self, governance_service, mock_governance_repo):
        """Test creating content review request"""
        mock_review = ContentReviewRequest(
            content_type=ContentType.CHARACTER,
            content_data={"canonical_name": "Iron Man", "universe": "marvel"},
            submitted_by="user-123"
        )
        mock_governance_repo.create_content_review_request.return_value = mock_review
        
        review = await governance_service.create_content_review_request(
            content_type=ContentType.CHARACTER,
            content_data={"canonical_name": "Iron Man", "universe": "marvel"},
            submitted_by="user-123"
        )
        
        assert review.content_type == ContentType.CHARACTER
        assert review.submitted_by == "user-123"
        mock_governance_repo.create_content_review_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_approve_content_review(self, governance_service, mock_governance_repo):
        """Test approving content review"""
        review = ContentReviewRequest(
            content_type=ContentType.CHARACTER,
            content_data={"canonical_name": "Iron Man", "universe": "marvel"},
            submitted_by="user-123"
        )
        
        mock_governance_repo.get_content_review_request.return_value = review
        mock_governance_repo.update_content_review_request.return_value = review
        
        # Mock the _process_approved_content method
        with patch.object(governance_service, '_process_approved_content', new_callable=AsyncMock):
            updated_review = await governance_service.approve_content_review("review-123", "admin-456")
        
        assert "admin-456" in updated_review.approvals
        mock_governance_repo.update_content_review_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_generate_governance_report(self, governance_service, mock_governance_repo):
        """Test generating governance report"""
        mock_governance_repo.get_duplicate_detections.return_value = []
        mock_governance_repo.create_governance_report.return_value = ContentGovernanceReport(
            report_type="duplicate_analysis",
            generated_by="admin-123"
        )
        
        report = await governance_service.generate_governance_report(
            report_type="duplicate_analysis",
            filters={"universe": "marvel"},
            generated_by="admin-123"
        )
        
        assert report.report_type == "duplicate_analysis"
        assert report.generated_by == "admin-123"
        mock_governance_repo.create_governance_report.assert_called_once()


class TestDuplicateDetection:
    """Test duplicate detection model"""
    
    def test_create_duplicate_detection(self):
        """Test creating duplicate detection"""
        duplicate = DuplicateDetection(
            character_name="Spiderman",
            universe="marvel",
            duplicate_type=DuplicateType.SIMILAR_NAME,
            confidence_score=0.85,
            existing_character_name="Spider-Man",
            suggested_action="Review - high similarity, check if same character"
        )
        
        assert duplicate.character_name == "Spiderman"
        assert duplicate.duplicate_type == DuplicateType.SIMILAR_NAME
        assert duplicate.confidence_score == 0.85
        assert duplicate.resolved is False
    
    def test_confidence_score_validation(self):
        """Test confidence score validation"""
        # Valid confidence score
        duplicate = DuplicateDetection(
            character_name="Test",
            universe="marvel",
            duplicate_type=DuplicateType.SIMILAR_NAME,
            confidence_score=0.5,
            suggested_action="Test"
        )
        assert duplicate.confidence_score == 0.5
        
        # Invalid confidence scores should raise validation error
        with pytest.raises(ValueError):
            DuplicateDetection(
                character_name="Test",
                universe="marvel",
                duplicate_type=DuplicateType.SIMILAR_NAME,
                confidence_score=1.5,  # > 1.0
                suggested_action="Test"
            )
        
        with pytest.raises(ValueError):
            DuplicateDetection(
                character_name="Test",
                universe="marvel",
                duplicate_type=DuplicateType.SIMILAR_NAME,
                confidence_score=-0.1,  # < 0.0
                suggested_action="Test"
            )


if __name__ == "__main__":
    pytest.main([__file__])