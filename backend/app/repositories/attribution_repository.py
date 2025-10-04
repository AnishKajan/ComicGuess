"""
Attribution repository for managing IP compliance data in Cosmos DB
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.repositories.base import BaseRepository
from app.models.attribution import (
    Attribution, 
    AttributionDisplay, 
    IPComplianceReport,
    TakedownRequest,
    RightsHolder,
    LicenseType
)
from app.config import settings
from app.database.exceptions import ItemNotFoundError

logger = logging.getLogger(__name__)

class AttributionRepository(BaseRepository[Attribution]):
    """Repository for attribution and IP compliance data"""
    
    def __init__(self):
        super().__init__(settings.cosmos_container_attributions)
    
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key (character_name for attributions)"""
        return 'character_name' in item and item['character_name'] == partition_key
    
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item (character_name for attributions)"""
        item['character_name'] = partition_key
        return item
    
    async def create_attribution(self, attribution: Attribution) -> Attribution:
        """Create a new attribution record"""
        attribution_dict = attribution.model_dump()
        result = await self.create(attribution_dict, attribution.character_name)
        return Attribution(**result)
    
    async def get_attribution_by_character(self, character_name: str) -> Optional[Attribution]:
        """Get attribution by character name"""
        result = await self.get_by_id(character_name, character_name)
        if result:
            return Attribution(**result)
        return None
    
    async def update_attribution(self, attribution: Attribution) -> Attribution:
        """Update an existing attribution record"""
        attribution.updated_at = datetime.utcnow()
        attribution_dict = attribution.model_dump()
        result = await self.update(attribution_dict, attribution.character_name)
        return Attribution(**result)
    
    async def get_attributions_by_rights_holder(self, rights_holder: RightsHolder) -> List[Attribution]:
        """Get all attributions for a specific rights holder"""
        query = """
        SELECT * FROM c 
        WHERE c.rights_holder = @rights_holder
        ORDER BY c.character_name ASC
        """
        parameters = [{"name": "@rights_holder", "value": rights_holder.value}]
        
        results = await self.query(query, parameters)
        return [Attribution(**result) for result in results]
    
    async def get_attributions_by_license_type(self, license_type: LicenseType) -> List[Attribution]:
        """Get all attributions by license type"""
        query = """
        SELECT * FROM c 
        WHERE c.license_type = @license_type
        ORDER BY c.character_name ASC
        """
        parameters = [{"name": "@license_type", "value": license_type.value}]
        
        results = await self.query(query, parameters)
        return [Attribution(**result) for result in results]
    
    async def get_characters_missing_attribution(self, character_names: List[str]) -> List[str]:
        """Get list of characters that don't have attribution records"""
        if not character_names:
            return []
        
        # Build query to check which characters have attribution
        placeholders = ", ".join([f"@char{i}" for i in range(len(character_names))])
        query = f"""
        SELECT VALUE c.character_name FROM c 
        WHERE c.character_name IN ({placeholders})
        """
        
        parameters = [
            {"name": f"@char{i}", "value": name} 
            for i, name in enumerate(character_names)
        ]
        
        attributed_characters = await self.query(query, parameters)
        attributed_set = set(attributed_characters)
        
        return [name for name in character_names if name not in attributed_set]
    
    async def generate_compliance_report(self, character_names: List[str]) -> IPComplianceReport:
        """Generate IP compliance report"""
        total_characters = len(character_names)
        missing_attribution = await self.get_characters_missing_attribution(character_names)
        attributed_characters = total_characters - len(missing_attribution)
        
        # Get all attributions to analyze
        query = "SELECT * FROM c"
        all_attributions = await self.query(query, [])
        
        # Count by rights holder
        rights_holder_breakdown = {}
        license_type_breakdown = {}
        compliance_issues = []
        
        for attr_data in all_attributions:
            attr = Attribution(**attr_data)
            
            # Count rights holders
            rh = attr.rights_holder.value
            rights_holder_breakdown[rh] = rights_holder_breakdown.get(rh, 0) + 1
            
            # Count license types
            lt = attr.license_type.value
            license_type_breakdown[lt] = license_type_breakdown.get(lt, 0) + 1
            
            # Check for compliance issues
            if not attr.copyright_notice:
                compliance_issues.append(f"Missing copyright notice for {attr.character_name}")
            
            if not attr.attribution_text:
                compliance_issues.append(f"Missing attribution text for {attr.character_name}")
            
            if attr.license_type == LicenseType.FAIR_USE and not attr.legal_review_date:
                compliance_issues.append(f"Fair use claim for {attr.character_name} needs legal review")
        
        # Add missing attribution issues
        for missing_char in missing_attribution:
            compliance_issues.append(f"No attribution record for {missing_char}")
        
        return IPComplianceReport(
            total_characters=total_characters,
            attributed_characters=attributed_characters,
            missing_attribution=len(missing_attribution),
            rights_holder_breakdown=rights_holder_breakdown,
            license_type_breakdown=license_type_breakdown,
            compliance_issues=compliance_issues
        )
    
    async def get_display_attribution(self, character_name: str) -> Optional[AttributionDisplay]:
        """Get formatted attribution for display"""
        attribution = await self.get_attribution_by_character(character_name)
        if attribution:
            return AttributionDisplay.from_attribution(attribution)
        return None
    
    async def bulk_create_attributions(self, attributions: List[Attribution]) -> List[Attribution]:
        """Create multiple attribution records"""
        created_attributions = []
        
        for attribution in attributions:
            try:
                created = await self.create_attribution(attribution)
                created_attributions.append(created)
            except Exception as e:
                logger.error(f"Failed to create attribution for {attribution.character_name}: {e}")
                # Continue with other attributions
        
        logger.info(f"Created {len(created_attributions)} attribution records")
        return created_attributions
    
    async def update_legal_review_date(self, character_name: str, review_date: datetime) -> bool:
        """Update legal review date for a character"""
        attribution = await self.get_attribution_by_character(character_name)
        if attribution:
            attribution.legal_review_date = review_date
            attribution.updated_at = datetime.utcnow()
            await self.update_attribution(attribution)
            return True
        return False
    
    async def get_characters_needing_review(self, days_threshold: int = 365) -> List[Attribution]:
        """Get characters that need legal review"""
        cutoff_date = datetime.utcnow().replace(day=1)  # Start of current month
        cutoff_date = cutoff_date.replace(year=cutoff_date.year - (days_threshold // 365))
        
        query = """
        SELECT * FROM c 
        WHERE (c.legal_review_date IS NULL OR c.legal_review_date < @cutoff_date)
        AND c.license_type = @fair_use_type
        ORDER BY c.character_name ASC
        """
        parameters = [
            {"name": "@cutoff_date", "value": cutoff_date.isoformat()},
            {"name": "@fair_use_type", "value": LicenseType.FAIR_USE.value}
        ]
        
        results = await self.query(query, parameters)
        return [Attribution(**result) for result in results]

class TakedownRequestRepository(BaseRepository[TakedownRequest]):
    """Repository for managing IP takedown requests"""
    
    def __init__(self):
        super().__init__(settings.cosmos_container_takedown_requests)
    
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key (id for takedown requests)"""
        return 'id' in item and item['id'] == partition_key
    
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item (id for takedown requests)"""
        item['id'] = partition_key
        return item
    
    async def create_takedown_request(self, request: TakedownRequest) -> TakedownRequest:
        """Create a new takedown request"""
        request_dict = request.model_dump()
        result = await self.create(request_dict, request.id)
        return TakedownRequest(**result)
    
    async def get_takedown_request(self, request_id: str) -> Optional[TakedownRequest]:
        """Get takedown request by ID"""
        result = await self.get_by_id(request_id, request_id)
        if result:
            return TakedownRequest(**result)
        return None
    
    async def update_takedown_request(self, request: TakedownRequest) -> TakedownRequest:
        """Update takedown request"""
        request_dict = request.model_dump()
        result = await self.update(request_dict, request.id)
        return TakedownRequest(**result)
    
    async def get_pending_requests(self) -> List[TakedownRequest]:
        """Get all pending takedown requests"""
        query = """
        SELECT * FROM c 
        WHERE c.status = @status
        ORDER BY c.received_at ASC
        """
        parameters = [{"name": "@status", "value": "pending"}]
        
        results = await self.query(query, parameters)
        return [TakedownRequest(**result) for result in results]
    
    async def get_requests_by_character(self, character_name: str) -> List[TakedownRequest]:
        """Get all takedown requests for a specific character"""
        query = """
        SELECT * FROM c 
        WHERE c.character_name = @character_name
        ORDER BY c.received_at DESC
        """
        parameters = [{"name": "@character_name", "value": character_name}]
        
        results = await self.query(query, parameters)
        return [TakedownRequest(**result) for result in results]
    
    async def mark_content_removed(self, request_id: str) -> bool:
        """Mark content as removed for a takedown request"""
        request = await self.get_takedown_request(request_id)
        if request:
            request.content_removed = True
            request.removal_date = datetime.utcnow()
            request.status = "completed"
            request.processed_at = datetime.utcnow()
            await self.update_takedown_request(request)
            return True
        return False