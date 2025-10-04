"""
IP Compliance Service for managing intellectual property compliance,
attribution, and takedown requests.
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

from app.models.attribution import (
    Attribution,
    AttributionDisplay, 
    IPComplianceReport,
    TakedownRequest,
    RightsHolder,
    LicenseType,
    generate_standard_attribution,
    get_rights_holder_from_universe
)
from app.repositories.attribution_repository import AttributionRepository, TakedownRequestRepository
from app.repositories.puzzle_repository import PuzzleRepository
from app.models.puzzle import Puzzle

logger = logging.getLogger(__name__)

class IPComplianceService:
    """Service for managing IP compliance and attribution"""
    
    def __init__(self):
        self.attribution_repo = AttributionRepository()
        self.takedown_repo = TakedownRequestRepository()
        self.puzzle_repo = PuzzleRepository()
    
    async def ensure_character_attribution(self, character_name: str, universe: str) -> Attribution:
        """Ensure a character has proper attribution, creating if missing"""
        
        # Check if attribution already exists
        existing = await self.attribution_repo.get_attribution_by_character(character_name)
        if existing:
            return existing
        
        # Create standard attribution
        rights_holder = get_rights_holder_from_universe(universe)
        attribution = generate_standard_attribution(
            character_name=character_name,
            rights_holder=rights_holder
        )
        
        # Save to database
        created = await self.attribution_repo.create_attribution(attribution)
        logger.info(f"Created attribution for character: {character_name}")
        
        return created
    
    async def get_character_display_attribution(self, character_name: str) -> Optional[AttributionDisplay]:
        """Get formatted attribution for character display"""
        return await self.attribution_repo.get_display_attribution(character_name)
    
    async def bulk_ensure_attributions(self, puzzles: List[Puzzle]) -> List[Attribution]:
        """Ensure all puzzles have proper attribution"""
        attributions = []
        
        for puzzle in puzzles:
            try:
                attribution = await self.ensure_character_attribution(
                    puzzle.character, 
                    puzzle.universe
                )
                attributions.append(attribution)
            except Exception as e:
                logger.error(f"Failed to ensure attribution for {puzzle.character}: {e}")
        
        return attributions
    
    async def generate_compliance_report(self) -> IPComplianceReport:
        """Generate comprehensive IP compliance report"""
        
        # Get all puzzles to check attribution coverage
        all_puzzles = await self.puzzle_repo.get_all_puzzles()
        character_names = [puzzle.character for puzzle in all_puzzles]
        
        return await self.attribution_repo.generate_compliance_report(character_names)
    
    async def update_character_attribution(
        self, 
        character_name: str,
        creator_names: Optional[str] = None,
        first_appearance: Optional[str] = None,
        image_source: Optional[str] = None,
        compliance_notes: Optional[str] = None
    ) -> Optional[Attribution]:
        """Update attribution information for a character"""
        
        attribution = await self.attribution_repo.get_attribution_by_character(character_name)
        if not attribution:
            logger.warning(f"No attribution found for character: {character_name}")
            return None
        
        # Update fields if provided
        if creator_names is not None:
            attribution.creator_names = creator_names
        
        if first_appearance is not None:
            attribution.first_appearance = first_appearance
        
        if image_source is not None:
            attribution.image_source = image_source
        
        if compliance_notes is not None:
            attribution.compliance_notes = compliance_notes
        
        # Regenerate attribution text with new information
        attribution_parts = [
            f"{attribution.character_name} is a trademark and copyright of {attribution.rights_holder.value}."
        ]
        
        if attribution.creator_names:
            attribution_parts.append(f"Created by {attribution.creator_names}.")
        
        if attribution.first_appearance:
            attribution_parts.append(f"First appeared in {attribution.first_appearance}.")
        
        attribution_parts.append(
            "Used under fair use for educational and entertainment purposes."
        )
        
        attribution.attribution_text = " ".join(attribution_parts)
        
        return await self.attribution_repo.update_attribution(attribution)
    
    async def mark_legal_review_completed(self, character_name: str) -> bool:
        """Mark legal review as completed for a character"""
        return await self.attribution_repo.update_legal_review_date(
            character_name, 
            datetime.utcnow()
        )
    
    async def get_characters_needing_review(self) -> List[Attribution]:
        """Get characters that need legal review"""
        return await self.attribution_repo.get_characters_needing_review()
    
    async def create_takedown_request(
        self,
        character_name: str,
        rights_holder: str,
        request_type: str,
        request_details: str,
        contact_email: str,
        contact_name: Optional[str] = None
    ) -> TakedownRequest:
        """Create a new takedown request"""
        
        request = TakedownRequest(
            id=str(uuid.uuid4()),
            character_name=character_name,
            rights_holder=rights_holder,
            request_type=request_type,
            request_details=request_details,
            contact_email=contact_email,
            contact_name=contact_name
        )
        
        created = await self.takedown_repo.create_takedown_request(request)
        logger.warning(f"Takedown request created for character: {character_name}")
        
        return created
    
    async def process_takedown_request(self, request_id: str, remove_content: bool = True) -> bool:
        """Process a takedown request"""
        
        request = await self.takedown_repo.get_takedown_request(request_id)
        if not request:
            return False
        
        if remove_content:
            # Remove character content
            success = await self.remove_character_content(request.character_name)
            if success:
                await self.takedown_repo.mark_content_removed(request_id)
                logger.info(f"Content removed for takedown request: {request_id}")
                return True
        
        return False
    
    async def remove_character_content(self, character_name: str) -> bool:
        """Remove all content for a character (puzzles, images, attribution)"""
        try:
            # Get all puzzles for this character
            puzzles = await self.puzzle_repo.get_puzzles_by_character(character_name)
            
            # Remove puzzles
            for puzzle in puzzles:
                await self.puzzle_repo.delete(puzzle.id, puzzle.id)
            
            # Remove attribution
            await self.attribution_repo.delete(character_name, character_name)
            
            logger.info(f"Removed all content for character: {character_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove content for {character_name}: {e}")
            return False
    
    async def get_pending_takedown_requests(self) -> List[TakedownRequest]:
        """Get all pending takedown requests"""
        return await self.takedown_repo.get_pending_requests()
    
    async def validate_fair_use_compliance(self, character_name: str) -> Dict[str, Any]:
        """Validate fair use compliance for a character"""
        
        attribution = await self.attribution_repo.get_attribution_by_character(character_name)
        if not attribution:
            return {
                "compliant": False,
                "issues": ["No attribution record found"],
                "recommendations": ["Create attribution record"]
            }
        
        issues = []
        recommendations = []
        
        # Check required fields
        if not attribution.copyright_notice:
            issues.append("Missing copyright notice")
            recommendations.append("Add copyright notice")
        
        if not attribution.attribution_text:
            issues.append("Missing attribution text")
            recommendations.append("Add attribution text")
        
        if attribution.license_type == LicenseType.FAIR_USE and not attribution.legal_review_date:
            issues.append("Fair use claim not legally reviewed")
            recommendations.append("Obtain legal review of fair use position")
        
        # Check educational purpose clarity
        if "educational" not in attribution.attribution_text.lower():
            issues.append("Educational purpose not clearly stated")
            recommendations.append("Clarify educational purpose in attribution")
        
        return {
            "compliant": len(issues) == 0,
            "issues": issues,
            "recommendations": recommendations,
            "attribution": attribution.model_dump() if attribution else None
        }
    
    async def generate_attribution_report_by_universe(self, universe: str) -> Dict[str, Any]:
        """Generate attribution report for a specific universe"""
        
        rights_holder = get_rights_holder_from_universe(universe)
        attributions = await self.attribution_repo.get_attributions_by_rights_holder(rights_holder)
        
        # Get puzzles for this universe
        puzzles = await self.puzzle_repo.get_puzzles_by_universe(universe)
        puzzle_characters = [p.character for p in puzzles]
        
        # Find missing attributions
        attributed_characters = [a.character_name for a in attributions]
        missing_attributions = [
            char for char in puzzle_characters 
            if char not in attributed_characters
        ]
        
        return {
            "universe": universe,
            "rights_holder": rights_holder.value,
            "total_characters": len(puzzle_characters),
            "attributed_characters": len(attributed_characters),
            "missing_attributions": missing_attributions,
            "attribution_coverage": len(attributed_characters) / len(puzzle_characters) if puzzle_characters else 0,
            "attributions": [a.model_dump() for a in attributions]
        }
    
    async def export_attribution_data(self) -> Dict[str, Any]:
        """Export all attribution data for backup/audit purposes"""
        
        # Get all attributions
        query = "SELECT * FROM c ORDER BY c.character_name ASC"
        all_attributions = await self.attribution_repo.query(query, [])
        
        # Get all takedown requests
        query = "SELECT * FROM c ORDER BY c.received_at DESC"
        all_requests = await self.takedown_repo.query(query, [])
        
        return {
            "export_date": datetime.utcnow().isoformat(),
            "total_attributions": len(all_attributions),
            "total_takedown_requests": len(all_requests),
            "attributions": all_attributions,
            "takedown_requests": all_requests
        }
    
    async def import_attribution_data(self, attribution_data: List[Dict[str, Any]]) -> int:
        """Import attribution data from external source"""
        
        imported_count = 0
        
        for attr_data in attribution_data:
            try:
                attribution = Attribution(**attr_data)
                await self.attribution_repo.create_attribution(attribution)
                imported_count += 1
            except Exception as e:
                logger.error(f"Failed to import attribution: {e}")
        
        logger.info(f"Imported {imported_count} attribution records")
        return imported_count