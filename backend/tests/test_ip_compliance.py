"""
Tests for IP compliance functionality including attribution and takedown handling
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.attribution import (
    Attribution, 
    AttributionDisplay,
    TakedownRequest,
    RightsHolder,
    LicenseType,
    generate_standard_attribution,
    get_rights_holder_from_universe
)
from app.models.puzzle import Puzzle
from app.services.ip_compliance_service import IPComplianceService

client = TestClient(app)

@pytest.fixture
def mock_attribution():
    """Mock attribution for testing"""
    return Attribution(
        character_name="Spider-Man",
        rights_holder=RightsHolder.MARVEL,
        copyright_notice="© 2024 Marvel Comics. All rights reserved.",
        license_type=LicenseType.FAIR_USE,
        attribution_text="Spider-Man is a trademark and copyright of Marvel Comics. Created by Stan Lee and Steve Ditko. First appeared in Amazing Fantasy #15. Used under fair use for educational and entertainment purposes.",
        creator_names="Stan Lee and Steve Ditko",
        first_appearance="Amazing Fantasy #15",
        legal_review_date=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )

@pytest.fixture
def mock_puzzle():
    """Mock puzzle for testing"""
    return Puzzle(
        id="20240115-marvel",
        universe="marvel",
        character="Spider-Man",
        character_aliases=["Spiderman", "Peter Parker"],
        image_key="marvel/spider-man.jpg",
        active_date="2024-01-15"
    )

@pytest.fixture
def mock_takedown_request():
    """Mock takedown request for testing"""
    return TakedownRequest(
        id="takedown-123",
        character_name="Spider-Man",
        rights_holder="Marvel Entertainment",
        request_type="DMCA",
        request_details="Unauthorized use of Spider-Man character",
        contact_email="legal@marvel.com",
        contact_name="Marvel Legal Team"
    )

class TestAttributionModels:
    """Test attribution model functionality"""

    def test_generate_standard_attribution(self):
        """Test standard attribution generation"""
        attribution = generate_standard_attribution(
            character_name="Batman",
            rights_holder=RightsHolder.DC,
            creator_names="Bob Kane and Bill Finger",
            first_appearance="Detective Comics #27"
        )
        
        assert attribution.character_name == "Batman"
        assert attribution.rights_holder == RightsHolder.DC
        assert attribution.license_type == LicenseType.FAIR_USE
        assert "Bob Kane and Bill Finger" in attribution.attribution_text
        assert "Detective Comics #27" in attribution.attribution_text
        assert "fair use" in attribution.attribution_text.lower()

    def test_get_rights_holder_from_universe(self):
        """Test rights holder mapping from universe"""
        assert get_rights_holder_from_universe("marvel") == RightsHolder.MARVEL
        assert get_rights_holder_from_universe("dc") == RightsHolder.DC
        assert get_rights_holder_from_universe("image") == RightsHolder.IMAGE
        assert get_rights_holder_from_universe("unknown") == RightsHolder.OTHER

    def test_attribution_display_creation(self, mock_attribution):
        """Test attribution display formatting"""
        display = AttributionDisplay.from_attribution(mock_attribution)
        
        assert display.character_name == "Spider-Man"
        assert "Marvel Comics" in display.short_attribution
        assert "Stan Lee and Steve Ditko" in display.full_attribution
        assert "Amazing Fantasy #15" in display.full_attribution
        assert "fair use" in display.fair_use_disclaimer.lower()

class TestIPComplianceService:
    """Test IP compliance service functionality"""

    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_ensure_character_attribution_existing(self, mock_puzzle_repo, mock_attr_repo, mock_attribution):
        """Test ensuring attribution when it already exists"""
        mock_attr_repo.return_value.get_attribution_by_character.return_value = mock_attribution
        
        service = IPComplianceService()
        result = await service.ensure_character_attribution("Spider-Man", "marvel")
        
        assert result == mock_attribution
        mock_attr_repo.return_value.create_attribution.assert_not_called()

    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_ensure_character_attribution_new(self, mock_puzzle_repo, mock_attr_repo):
        """Test ensuring attribution when creating new"""
        mock_attr_repo.return_value.get_attribution_by_character.return_value = None
        mock_attr_repo.return_value.create_attribution.return_value = AsyncMock()
        
        service = IPComplianceService()
        await service.ensure_character_attribution("Batman", "dc")
        
        mock_attr_repo.return_value.create_attribution.assert_called_once()
        
        # Verify the created attribution has correct properties
        call_args = mock_attr_repo.return_value.create_attribution.call_args[0][0]
        assert call_args.character_name == "Batman"
        assert call_args.rights_holder == RightsHolder.DC

    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_bulk_ensure_attributions(self, mock_puzzle_repo, mock_attr_repo, mock_puzzle):
        """Test bulk attribution creation"""
        mock_attr_repo.return_value.get_attribution_by_character.return_value = None
        mock_attr_repo.return_value.create_attribution.return_value = AsyncMock()
        
        service = IPComplianceService()
        puzzles = [mock_puzzle]
        
        await service.bulk_ensure_attributions(puzzles)
        
        mock_attr_repo.return_value.create_attribution.assert_called_once()

    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_validate_fair_use_compliance_compliant(self, mock_puzzle_repo, mock_attr_repo, mock_attribution):
        """Test fair use validation for compliant character"""
        mock_attr_repo.return_value.get_attribution_by_character.return_value = mock_attribution
        
        service = IPComplianceService()
        result = await service.validate_fair_use_compliance("Spider-Man")
        
        assert result["compliant"] is True
        assert len(result["issues"]) == 0

    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_validate_fair_use_compliance_non_compliant(self, mock_puzzle_repo, mock_attr_repo):
        """Test fair use validation for non-compliant character"""
        # Create attribution with missing fields
        incomplete_attribution = Attribution(
            character_name="Test Character",
            rights_holder=RightsHolder.MARVEL,
            copyright_notice="",  # Missing
            license_type=LicenseType.FAIR_USE,
            attribution_text=""  # Missing
        )
        
        mock_attr_repo.return_value.get_attribution_by_character.return_value = incomplete_attribution
        
        service = IPComplianceService()
        result = await service.validate_fair_use_compliance("Test Character")
        
        assert result["compliant"] is False
        assert "Missing copyright notice" in result["issues"]
        assert "Missing attribution text" in result["issues"]

class TestTakedownHandling:
    """Test takedown request handling"""

    @patch('app.services.ip_compliance_service.TakedownRequestRepository')
    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_create_takedown_request(self, mock_puzzle_repo, mock_attr_repo, mock_takedown_repo):
        """Test takedown request creation"""
        mock_takedown_repo.return_value.create_takedown_request.return_value = AsyncMock()
        
        service = IPComplianceService()
        await service.create_takedown_request(
            character_name="Spider-Man",
            rights_holder="Marvel Entertainment",
            request_type="DMCA",
            request_details="Unauthorized use",
            contact_email="legal@marvel.com"
        )
        
        mock_takedown_repo.return_value.create_takedown_request.assert_called_once()

    @patch('app.services.ip_compliance_service.TakedownRequestRepository')
    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_process_takedown_request(self, mock_puzzle_repo, mock_attr_repo, mock_takedown_repo, mock_takedown_request):
        """Test takedown request processing"""
        mock_takedown_repo.return_value.get_takedown_request.return_value = mock_takedown_request
        mock_takedown_repo.return_value.mark_content_removed.return_value = True
        mock_puzzle_repo.return_value.get_puzzles_by_character.return_value = []
        mock_attr_repo.return_value.delete.return_value = True
        
        service = IPComplianceService()
        result = await service.process_takedown_request("takedown-123", remove_content=True)
        
        assert result is True
        mock_takedown_repo.return_value.mark_content_removed.assert_called_once_with("takedown-123")

class TestIPComplianceAPI:
    """Test IP compliance API endpoints"""

    @patch('app.api.ip_compliance.IPComplianceService')
    def test_get_character_attribution_success(self, mock_service):
        """Test successful character attribution retrieval"""
        mock_display = AttributionDisplay(
            character_name="Spider-Man",
            short_attribution="© Marvel Comics",
            full_attribution="Spider-Man © Marvel Comics | Created by Stan Lee and Steve Ditko",
            copyright_notice="© 2024 Marvel Comics. All rights reserved.",
            fair_use_disclaimer="Used under fair use for educational purposes."
        )
        
        mock_service.return_value.get_character_display_attribution.return_value = mock_display
        
        response = client.get("/api/ip-compliance/attribution/Spider-Man")
        
        assert response.status_code == 200
        data = response.json()
        assert data["character_name"] == "Spider-Man"
        assert "Marvel Comics" in data["short_attribution"]

    @patch('app.api.ip_compliance.IPComplianceService')
    def test_get_character_attribution_not_found(self, mock_service):
        """Test character attribution not found"""
        mock_service.return_value.get_character_display_attribution.return_value = None
        
        response = client.get("/api/ip-compliance/attribution/Unknown-Character")
        
        assert response.status_code == 404
        assert "No attribution found" in response.json()["detail"]

    @patch('app.api.ip_compliance.IPComplianceService')
    def test_create_takedown_request_success(self, mock_service):
        """Test successful takedown request creation"""
        mock_request = TakedownRequest(
            id="takedown-123",
            character_name="Spider-Man",
            rights_holder="Marvel Entertainment",
            request_type="DMCA",
            request_details="Unauthorized use",
            contact_email="legal@marvel.com"
        )
        
        mock_service.return_value.create_takedown_request.return_value = mock_request
        
        response = client.post(
            "/api/ip-compliance/takedown-request",
            params={
                "character_name": "Spider-Man",
                "rights_holder": "Marvel Entertainment",
                "request_type": "DMCA",
                "request_details": "Unauthorized use",
                "contact_email": "legal@marvel.com"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["character_name"] == "Spider-Man"
        assert data["request_type"] == "DMCA"

class TestComplianceReporting:
    """Test compliance reporting functionality"""

    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_generate_compliance_report(self, mock_puzzle_repo, mock_attr_repo, mock_puzzle):
        """Test compliance report generation"""
        mock_puzzle_repo.return_value.get_all_puzzles.return_value = [mock_puzzle]
        mock_attr_repo.return_value.generate_compliance_report.return_value = AsyncMock()
        
        service = IPComplianceService()
        await service.generate_compliance_report()
        
        mock_attr_repo.return_value.generate_compliance_report.assert_called_once()

    @patch('app.services.ip_compliance_service.AttributionRepository')
    @patch('app.services.ip_compliance_service.PuzzleRepository')
    async def test_generate_universe_report(self, mock_puzzle_repo, mock_attr_repo, mock_puzzle):
        """Test universe-specific attribution report"""
        mock_puzzle_repo.return_value.get_puzzles_by_universe.return_value = [mock_puzzle]
        mock_attr_repo.return_value.get_attributions_by_rights_holder.return_value = []
        
        service = IPComplianceService()
        report = await service.generate_attribution_report_by_universe("marvel")
        
        assert report["universe"] == "marvel"
        assert report["rights_holder"] == "Marvel Comics"
        assert report["total_characters"] == 1

class TestDataMinimizationCompliance:
    """Test data minimization for COPPA compliance"""

    def test_attribution_model_minimal_fields(self):
        """Test that attribution model contains only necessary fields"""
        attribution = Attribution(
            character_name="Test Character",
            rights_holder=RightsHolder.MARVEL,
            copyright_notice="© Test",
            license_type=LicenseType.FAIR_USE,
            attribution_text="Test attribution"
        )
        
        required_fields = {
            'character_name', 'rights_holder', 'copyright_notice', 
            'license_type', 'attribution_text', 'created_at'
        }
        
        actual_fields = set(attribution.model_dump().keys())
        
        # Allow for optional fields that support compliance
        allowed_optional_fields = {
            'creator_names', 'first_appearance', 'trademark_info',
            'image_source', 'image_copyright', 'image_license',
            'legal_review_date', 'compliance_notes', 'updated_at'
        }
        
        unexpected_fields = actual_fields - required_fields - allowed_optional_fields
        assert not unexpected_fields, f"Unexpected fields in attribution model: {unexpected_fields}"

    def test_takedown_request_minimal_fields(self):
        """Test that takedown request model contains only necessary fields"""
        request = TakedownRequest(
            id="test-id",
            character_name="Test Character",
            rights_holder="Test Holder",
            request_type="DMCA",
            request_details="Test details",
            contact_email="test@example.com"
        )
        
        required_fields = {
            'id', 'character_name', 'rights_holder', 'request_type',
            'request_details', 'contact_email', 'status', 'received_at',
            'content_removed', 'legal_review_required'
        }
        
        actual_fields = set(request.model_dump().keys())
        
        # Allow for optional fields that support compliance tracking
        allowed_optional_fields = {
            'contact_name', 'processed_at', 'response_sent_at',
            'removal_date', 'internal_notes'
        }
        
        unexpected_fields = actual_fields - required_fields - allowed_optional_fields
        assert not unexpected_fields, f"Unexpected fields in takedown request model: {unexpected_fields}"

class TestLegalCompliance:
    """Test legal compliance features"""

    def test_fair_use_disclaimer_present(self, mock_attribution):
        """Test that fair use disclaimers are present"""
        display = AttributionDisplay.from_attribution(mock_attribution)
        
        assert "fair use" in display.fair_use_disclaimer.lower()
        assert "educational" in display.fair_use_disclaimer.lower()
        assert "entertainment" in display.fair_use_disclaimer.lower()

    def test_copyright_notice_format(self, mock_attribution):
        """Test copyright notice formatting"""
        assert "©" in mock_attribution.copyright_notice
        assert "Marvel Comics" in mock_attribution.copyright_notice
        assert "All rights reserved" in mock_attribution.copyright_notice

    def test_attribution_text_completeness(self, mock_attribution):
        """Test attribution text includes all required elements"""
        text = mock_attribution.attribution_text.lower()
        
        assert "trademark" in text
        assert "copyright" in text
        assert "created by" in text
        assert "fair use" in text
        assert "educational" in text