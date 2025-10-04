"""Repository for content governance data operations"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.repositories.base import BaseRepository
from app.models.content_governance import (
    CanonicalCharacter,
    DuplicateDetection,
    ContentReviewRequest,
    ContentGovernanceRule,
    ContentGovernanceReport,
    ContentStatus,
    ContentType
)
from app.config import settings
from app.database.exceptions import ItemNotFoundError, DuplicateItemError

logger = logging.getLogger(__name__)


class ContentGovernanceRepository(BaseRepository):
    """Repository for content governance operations"""
    
    def __init__(self):
        # Use a dedicated container for governance data
        super().__init__(settings.cosmos_container_governance)
    
    def _has_partition_key(self, item: Dict[str, Any], partition_key: str) -> bool:
        """Check if item has the required partition key"""
        return 'id' in item and item['id'] == partition_key
    
    def _add_partition_key(self, item: Dict[str, Any], partition_key: str) -> Dict[str, Any]:
        """Add partition key to item"""
        item['id'] = partition_key
        return item
    
    # Canonical Character operations
    
    async def create_canonical_character(self, character: CanonicalCharacter) -> CanonicalCharacter:
        """Create a new canonical character"""
        character_dict = character.model_dump()
        character_dict['document_type'] = 'canonical_character'
        
        result = await self.create(character_dict, character.id)
        return CanonicalCharacter(**result)
    
    async def get_canonical_character(self, character_id: str) -> Optional[CanonicalCharacter]:
        """Get canonical character by ID"""
        result = await self.get_by_id(character_id, character_id)
        if result and result.get('document_type') == 'canonical_character':
            return CanonicalCharacter(**result)
        return None
    
    async def get_canonical_characters_by_universe(self, universe: str) -> List[CanonicalCharacter]:
        """Get all canonical characters for a universe"""
        query = """
        SELECT * FROM c 
        WHERE c.document_type = 'canonical_character' 
        AND c.universe = @universe
        ORDER BY c.canonical_name
        """
        parameters = [{"name": "@universe", "value": universe}]
        
        results = await self.query(query, parameters)
        return [CanonicalCharacter(**result) for result in results]
    
    async def update_canonical_character(self, character: CanonicalCharacter) -> CanonicalCharacter:
        """Update canonical character"""
        character_dict = character.model_dump()
        character_dict['document_type'] = 'canonical_character'
        
        result = await self.update(character_dict, character.id)
        return CanonicalCharacter(**result)
    
    async def delete_canonical_character(self, character_id: str) -> bool:
        """Delete canonical character"""
        return await self.delete(character_id, character_id)
    
    async def search_canonical_characters(self, search_term: str, universe: Optional[str] = None) -> List[CanonicalCharacter]:
        """Search canonical characters by name or alias"""
        if universe:
            query = """
            SELECT * FROM c 
            WHERE c.document_type = 'canonical_character'
            AND c.universe = @universe
            AND (CONTAINS(LOWER(c.canonical_name), @search_term)
                 OR EXISTS(SELECT VALUE alias FROM alias IN c.approved_aliases WHERE CONTAINS(LOWER(alias), @search_term)))
            ORDER BY c.canonical_name
            """
            parameters = [
                {"name": "@universe", "value": universe},
                {"name": "@search_term", "value": search_term.lower()}
            ]
        else:
            query = """
            SELECT * FROM c 
            WHERE c.document_type = 'canonical_character'
            AND (CONTAINS(LOWER(c.canonical_name), @search_term)
                 OR EXISTS(SELECT VALUE alias FROM alias IN c.approved_aliases WHERE CONTAINS(LOWER(alias), @search_term)))
            ORDER BY c.canonical_name
            """
            parameters = [{"name": "@search_term", "value": search_term.lower()}]
        
        results = await self.query(query, parameters)
        return [CanonicalCharacter(**result) for result in results]
    
    # Duplicate Detection operations
    
    async def create_duplicate_detection(self, duplicate: DuplicateDetection) -> DuplicateDetection:
        """Create a duplicate detection record"""
        duplicate_dict = duplicate.model_dump()
        duplicate_dict['document_type'] = 'duplicate_detection'
        
        result = await self.create(duplicate_dict, duplicate.id)
        return DuplicateDetection(**result)
    
    async def get_duplicate_detection(self, duplicate_id: str) -> Optional[DuplicateDetection]:
        """Get duplicate detection by ID"""
        result = await self.get_by_id(duplicate_id, duplicate_id)
        if result and result.get('document_type') == 'duplicate_detection':
            return DuplicateDetection(**result)
        return None
    
    async def get_duplicate_detections(self, universe: Optional[str] = None, resolved: Optional[bool] = None,
                                     resolved_before: Optional[datetime] = None) -> List[DuplicateDetection]:
        """Get duplicate detections with filters"""
        conditions = ["c.document_type = 'duplicate_detection'"]
        parameters = []
        
        if universe:
            conditions.append("c.universe = @universe")
            parameters.append({"name": "@universe", "value": universe})
        
        if resolved is not None:
            conditions.append("c.resolved = @resolved")
            parameters.append({"name": "@resolved", "value": resolved})
        
        if resolved_before:
            conditions.append("c.resolved_at < @resolved_before")
            parameters.append({"name": "@resolved_before", "value": resolved_before.isoformat()})
        
        query = f"SELECT * FROM c WHERE {' AND '.join(conditions)} ORDER BY c.detected_at DESC"
        
        results = await self.query(query, parameters)
        return [DuplicateDetection(**result) for result in results]
    
    async def update_duplicate_detection(self, duplicate: DuplicateDetection) -> DuplicateDetection:
        """Update duplicate detection"""
        duplicate_dict = duplicate.model_dump()
        duplicate_dict['document_type'] = 'duplicate_detection'
        
        result = await self.update(duplicate_dict, duplicate.id)
        return DuplicateDetection(**result)
    
    async def delete_duplicate_detection(self, duplicate_id: str) -> bool:
        """Delete duplicate detection"""
        return await self.delete(duplicate_id, duplicate_id)
    
    # Content Review Request operations
    
    async def create_content_review_request(self, review: ContentReviewRequest) -> ContentReviewRequest:
        """Create a content review request"""
        review_dict = review.model_dump()
        review_dict['document_type'] = 'content_review_request'
        
        result = await self.create(review_dict, review.id)
        return ContentReviewRequest(**result)
    
    async def get_content_review_request(self, review_id: str) -> Optional[ContentReviewRequest]:
        """Get content review request by ID"""
        result = await self.get_by_id(review_id, review_id)
        if result and result.get('document_type') == 'content_review_request':
            return ContentReviewRequest(**result)
        return None
    
    async def get_content_review_requests(self, status: Optional[ContentStatus] = None,
                                        content_type: Optional[ContentType] = None,
                                        limit: int = 50, offset: int = 0) -> List[ContentReviewRequest]:
        """Get content review requests with filters"""
        conditions = ["c.document_type = 'content_review_request'"]
        parameters = []
        
        if status:
            conditions.append("c.status = @status")
            parameters.append({"name": "@status", "value": status.value})
        
        if content_type:
            conditions.append("c.content_type = @content_type")
            parameters.append({"name": "@content_type", "value": content_type.value})
        
        parameters.extend([
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit}
        ])
        
        query = f"""
        SELECT * FROM c 
        WHERE {' AND '.join(conditions)}
        ORDER BY c.priority DESC, c.submitted_at ASC
        OFFSET @offset LIMIT @limit
        """
        
        results = await self.query(query, parameters)
        return [ContentReviewRequest(**result) for result in results]
    
    async def update_content_review_request(self, review: ContentReviewRequest) -> ContentReviewRequest:
        """Update content review request"""
        review_dict = review.model_dump()
        review_dict['document_type'] = 'content_review_request'
        
        result = await self.update(review_dict, review.id)
        return ContentReviewRequest(**result)
    
    async def delete_content_review_request(self, review_id: str) -> bool:
        """Delete content review request"""
        return await self.delete(review_id, review_id)
    
    # Content Governance Rule operations
    
    async def create_governance_rule(self, rule: ContentGovernanceRule) -> ContentGovernanceRule:
        """Create a governance rule"""
        rule_dict = rule.model_dump()
        rule_dict['document_type'] = 'governance_rule'
        
        result = await self.create(rule_dict, rule.id)
        return ContentGovernanceRule(**result)
    
    async def get_governance_rule(self, rule_id: str) -> Optional[ContentGovernanceRule]:
        """Get governance rule by ID"""
        result = await self.get_by_id(rule_id, rule_id)
        if result and result.get('document_type') == 'governance_rule':
            return ContentGovernanceRule(**result)
        return None
    
    async def get_governance_rules(self, rule_type: Optional[str] = None, 
                                 universe: Optional[str] = None,
                                 is_active: bool = True) -> List[ContentGovernanceRule]:
        """Get governance rules with filters"""
        conditions = ["c.document_type = 'governance_rule'"]
        parameters = []
        
        if rule_type:
            conditions.append("c.rule_type = @rule_type")
            parameters.append({"name": "@rule_type", "value": rule_type})
        
        if universe:
            conditions.append("(c.universe = @universe OR c.universe = 'all')")
            parameters.append({"name": "@universe", "value": universe})
        
        conditions.append("c.is_active = @is_active")
        parameters.append({"name": "@is_active", "value": is_active})
        
        query = f"SELECT * FROM c WHERE {' AND '.join(conditions)} ORDER BY c.name"
        
        results = await self.query(query, parameters)
        return [ContentGovernanceRule(**result) for result in results]
    
    async def update_governance_rule(self, rule: ContentGovernanceRule) -> ContentGovernanceRule:
        """Update governance rule"""
        rule_dict = rule.model_dump()
        rule_dict['document_type'] = 'governance_rule'
        
        result = await self.update(rule_dict, rule.id)
        return ContentGovernanceRule(**result)
    
    async def delete_governance_rule(self, rule_id: str) -> bool:
        """Delete governance rule"""
        return await self.delete(rule_id, rule_id)
    
    # Content Governance Report operations
    
    async def create_governance_report(self, report: ContentGovernanceReport) -> ContentGovernanceReport:
        """Create a governance report"""
        report_dict = report.model_dump()
        report_dict['document_type'] = 'governance_report'
        
        result = await self.create(report_dict, report.id)
        return ContentGovernanceReport(**result)
    
    async def get_governance_report(self, report_id: str) -> Optional[ContentGovernanceReport]:
        """Get governance report by ID"""
        result = await self.get_by_id(report_id, report_id)
        if result and result.get('document_type') == 'governance_report':
            return ContentGovernanceReport(**result)
        return None
    
    async def get_governance_reports(self, report_type: Optional[str] = None,
                                   generated_by: Optional[str] = None,
                                   limit: int = 50) -> List[ContentGovernanceReport]:
        """Get governance reports with filters"""
        conditions = ["c.document_type = 'governance_report'"]
        parameters = []
        
        if report_type:
            conditions.append("c.report_type = @report_type")
            parameters.append({"name": "@report_type", "value": report_type})
        
        if generated_by:
            conditions.append("c.generated_by = @generated_by")
            parameters.append({"name": "@generated_by", "value": generated_by})
        
        parameters.append({"name": "@limit", "value": limit})
        
        query = f"""
        SELECT * FROM c 
        WHERE {' AND '.join(conditions)}
        ORDER BY c.generated_at DESC
        OFFSET 0 LIMIT @limit
        """
        
        results = await self.query(query, parameters)
        return [ContentGovernanceReport(**result) for result in results]
    
    async def delete_governance_report(self, report_id: str) -> bool:
        """Delete governance report"""
        return await self.delete(report_id, report_id)
    
    # Statistics and analytics
    
    async def get_governance_statistics(self) -> Dict[str, Any]:
        """Get governance statistics"""
        stats = {}
        
        # Count canonical characters by universe
        query = """
        SELECT c.universe, COUNT(1) as count
        FROM c 
        WHERE c.document_type = 'canonical_character'
        GROUP BY c.universe
        """
        results = await self.query(query)
        stats['characters_by_universe'] = {r['universe']: r['count'] for r in results}
        
        # Count pending reviews
        query = """
        SELECT VALUE COUNT(1) FROM c 
        WHERE c.document_type = 'content_review_request' 
        AND c.status = 'pending'
        """
        results = await self.query(query)
        stats['pending_reviews'] = results[0] if results else 0
        
        # Count unresolved duplicates
        query = """
        SELECT VALUE COUNT(1) FROM c 
        WHERE c.document_type = 'duplicate_detection' 
        AND c.resolved = false
        """
        results = await self.query(query)
        stats['unresolved_duplicates'] = results[0] if results else 0
        
        # Count active rules
        query = """
        SELECT VALUE COUNT(1) FROM c 
        WHERE c.document_type = 'governance_rule' 
        AND c.is_active = true
        """
        results = await self.query(query)
        stats['active_rules'] = results[0] if results else 0
        
        return stats
    
    async def cleanup_old_reports(self, days_to_keep: int = 90) -> int:
        """Clean up old governance reports"""
        cutoff_date = datetime.utcnow().replace(day=datetime.utcnow().day - days_to_keep)
        
        query = """
        SELECT c.id FROM c 
        WHERE c.document_type = 'governance_report'
        AND c.generated_at < @cutoff_date
        """
        parameters = [{"name": "@cutoff_date", "value": cutoff_date.isoformat()}]
        
        old_reports = await self.query(query, parameters)
        
        deleted_count = 0
        for report in old_reports:
            if await self.delete_governance_report(report['id']):
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old governance reports")
        return deleted_count