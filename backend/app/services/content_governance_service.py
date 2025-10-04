"""Content governance service for managing character names, aliases, and content review"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta

from app.models.content_governance import (
    CanonicalCharacter,
    DuplicateDetection,
    ContentReviewRequest,
    LocaleAwareNameMatcher,
    ContentGovernanceRule,
    ContentGovernanceReport,
    ContentStatus,
    ContentType,
    DuplicateType
)
from app.repositories.content_governance_repository import ContentGovernanceRepository
from app.repositories.puzzle_repository import PuzzleRepository
from app.models.puzzle import PuzzleCreate

logger = logging.getLogger(__name__)


class ContentGovernanceService:
    """Service for content governance operations"""
    
    def __init__(self):
        self.governance_repo = ContentGovernanceRepository()
        self.puzzle_repo = PuzzleRepository()
        self.name_matcher = LocaleAwareNameMatcher()
    
    async def create_canonical_character(self, canonical_name: str, universe: str, 
                                       approved_aliases: List[str], created_by: str,
                                       notes: Optional[str] = None) -> CanonicalCharacter:
        """Create a new canonical character entry"""
        # Check for duplicates first
        duplicates = await self.detect_character_duplicates(canonical_name, universe)
        if duplicates:
            logger.warning(f"Potential duplicates found for {canonical_name} in {universe}: {len(duplicates)}")
        
        character = CanonicalCharacter(
            canonical_name=canonical_name,
            universe=universe,
            approved_aliases=approved_aliases,
            created_by=created_by,
            notes=notes
        )
        
        return await self.governance_repo.create_canonical_character(character)
    
    async def get_canonical_character(self, character_id: str) -> Optional[CanonicalCharacter]:
        """Get canonical character by ID"""
        return await self.governance_repo.get_canonical_character(character_id)
    
    async def get_canonical_characters_by_universe(self, universe: str) -> List[CanonicalCharacter]:
        """Get all canonical characters for a universe"""
        return await self.governance_repo.get_canonical_characters_by_universe(universe)
    
    async def update_canonical_character(self, character_id: str, updates: Dict[str, Any]) -> CanonicalCharacter:
        """Update canonical character"""
        character = await self.governance_repo.get_canonical_character(character_id)
        if not character:
            raise ValueError(f"Canonical character {character_id} not found")
        
        # Apply updates
        for field, value in updates.items():
            if hasattr(character, field):
                setattr(character, field, value)
        
        character.updated_at = datetime.utcnow()
        
        return await self.governance_repo.update_canonical_character(character)
    
    async def add_character_alias(self, character_id: str, alias: str, admin_id: str) -> bool:
        """Add an alias to a canonical character"""
        character = await self.governance_repo.get_canonical_character(character_id)
        if not character:
            raise ValueError(f"Canonical character {character_id} not found")
        
        # Check for conflicts with other characters
        conflicts = await self.check_alias_conflicts(alias, character.universe, exclude_character_id=character_id)
        if conflicts:
            logger.warning(f"Alias conflicts found for '{alias}': {conflicts}")
            return False
        
        success = character.add_alias(alias)
        if success:
            await self.governance_repo.update_canonical_character(character)
            
            # Log the action
            logger.info(f"Admin {admin_id} added alias '{alias}' to character {character.canonical_name}")
        
        return success
    
    async def reject_character_alias(self, character_id: str, alias: str, admin_id: str) -> bool:
        """Reject an alias for a canonical character"""
        character = await self.governance_repo.get_canonical_character(character_id)
        if not character:
            raise ValueError(f"Canonical character {character_id} not found")
        
        success = character.reject_alias(alias)
        if success:
            await self.governance_repo.update_canonical_character(character)
            
            # Log the action
            logger.info(f"Admin {admin_id} rejected alias '{alias}' for character {character.canonical_name}")
        
        return success
    
    async def detect_character_duplicates(self, character_name: str, universe: str, 
                                        similarity_threshold: float = 0.8) -> List[DuplicateDetection]:
        """Detect potential duplicates for a character name"""
        # Get existing characters in the universe
        existing_characters = await self.governance_repo.get_canonical_characters_by_universe(universe)
        
        duplicates = []
        existing_names = []
        
        # Collect all names (canonical + aliases)
        for char in existing_characters:
            existing_names.extend(char.get_all_names())
        
        # Find potential duplicates
        potential_duplicates = self.name_matcher.find_potential_duplicates(
            character_name, existing_names, similarity_threshold
        )
        
        for dup in potential_duplicates:
            # Find which character this name belongs to
            existing_char = None
            for char in existing_characters:
                if dup["name"] in char.get_all_names():
                    existing_char = char
                    break
            
            duplicate_detection = DuplicateDetection(
                character_name=character_name,
                universe=universe,
                duplicate_type=dup["type"],
                confidence_score=dup["similarity"],
                existing_character_id=existing_char.id if existing_char else None,
                existing_character_name=existing_char.canonical_name if existing_char else dup["name"],
                suggested_action=self._get_suggested_action(dup["type"], dup["similarity"]),
                details={
                    "matching_name": dup["name"],
                    "similarity_score": dup["similarity"]
                }
            )
            
            duplicates.append(duplicate_detection)
        
        # Store duplicate detections for tracking
        for duplicate in duplicates:
            await self.governance_repo.create_duplicate_detection(duplicate)
        
        return duplicates
    
    def _get_suggested_action(self, duplicate_type: DuplicateType, confidence: float) -> str:
        """Get suggested action for resolving a duplicate"""
        if duplicate_type == DuplicateType.EXACT_MATCH:
            return "Reject - exact duplicate exists"
        elif confidence > 0.95:
            return "Review - very high similarity, likely duplicate"
        elif confidence > 0.85:
            return "Review - high similarity, check if same character"
        elif duplicate_type == DuplicateType.PHONETIC_MATCH:
            return "Review - phonetically similar, verify if different character"
        else:
            return "Monitor - low similarity, likely different character"
    
    async def check_alias_conflicts(self, alias: str, universe: str, 
                                  exclude_character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Check if an alias conflicts with existing characters"""
        existing_characters = await self.governance_repo.get_canonical_characters_by_universe(universe)
        
        conflicts = []
        
        for char in existing_characters:
            if exclude_character_id and char.id == exclude_character_id:
                continue
            
            # Check against canonical name and all aliases
            all_names = char.get_all_names()
            
            for name in all_names:
                similarity = self.name_matcher.calculate_similarity(alias, name)
                
                if similarity >= 0.9:  # High similarity threshold for conflicts
                    conflicts.append({
                        "character_id": char.id,
                        "character_name": char.canonical_name,
                        "conflicting_name": name,
                        "similarity": similarity,
                        "is_canonical": name == char.canonical_name
                    })
        
        return conflicts
    
    async def create_content_review_request(self, content_type: ContentType, content_data: Dict[str, Any],
                                          submitted_by: str, priority: int = 1) -> ContentReviewRequest:
        """Create a content review request"""
        review_request = ContentReviewRequest(
            content_type=content_type,
            content_data=content_data,
            submitted_by=submitted_by,
            priority=priority
        )
        
        return await self.governance_repo.create_content_review_request(review_request)
    
    async def get_pending_content_reviews(self, content_type: Optional[ContentType] = None,
                                        limit: int = 50) -> List[ContentReviewRequest]:
        """Get pending content review requests"""
        return await self.governance_repo.get_content_review_requests(
            status=ContentStatus.PENDING,
            content_type=content_type,
            limit=limit
        )
    
    async def approve_content_review(self, review_id: str, admin_id: str, 
                                   notes: Optional[str] = None) -> ContentReviewRequest:
        """Approve a content review request"""
        review = await self.governance_repo.get_content_review_request(review_id)
        if not review:
            raise ValueError(f"Content review {review_id} not found")
        
        review.add_approval(admin_id)
        if notes:
            review.review_notes = notes
        
        updated_review = await self.governance_repo.update_content_review_request(review)
        
        # If approved, process the content
        if updated_review.is_approved():
            await self._process_approved_content(updated_review)
        
        return updated_review
    
    async def reject_content_review(self, review_id: str, admin_id: str, 
                                  notes: Optional[str] = None) -> ContentReviewRequest:
        """Reject a content review request"""
        review = await self.governance_repo.get_content_review_request(review_id)
        if not review:
            raise ValueError(f"Content review {review_id} not found")
        
        review.add_rejection(admin_id, notes)
        
        return await self.governance_repo.update_content_review_request(review)
    
    async def _process_approved_content(self, review: ContentReviewRequest):
        """Process approved content based on type"""
        try:
            if review.content_type == ContentType.CHARACTER:
                await self._process_approved_character(review)
            elif review.content_type == ContentType.ALIAS:
                await self._process_approved_alias(review)
            elif review.content_type == ContentType.PUZZLE:
                await self._process_approved_puzzle(review)
            
            logger.info(f"Successfully processed approved {review.content_type.value}: {review.id}")
            
        except Exception as e:
            logger.error(f"Error processing approved content {review.id}: {e}")
            # Could implement retry logic or notification here
    
    async def _process_approved_character(self, review: ContentReviewRequest):
        """Process approved character"""
        data = review.content_data
        
        character = await self.create_canonical_character(
            canonical_name=data["canonical_name"],
            universe=data["universe"],
            approved_aliases=data.get("aliases", []),
            created_by=review.submitted_by,
            notes=f"Approved via review {review.id}"
        )
        
        logger.info(f"Created canonical character: {character.canonical_name}")
    
    async def _process_approved_alias(self, review: ContentReviewRequest):
        """Process approved alias"""
        data = review.content_data
        
        success = await self.add_character_alias(
            character_id=data["character_id"],
            alias=data["alias"],
            admin_id=review.submitted_by
        )
        
        if success:
            logger.info(f"Added alias '{data['alias']}' to character {data['character_id']}")
        else:
            logger.warning(f"Failed to add alias '{data['alias']}' - may have conflicts")
    
    async def _process_approved_puzzle(self, review: ContentReviewRequest):
        """Process approved puzzle"""
        data = review.content_data
        
        puzzle_create = PuzzleCreate(
            universe=data["universe"],
            character=data["character"],
            character_aliases=data.get("character_aliases", []),
            image_key=data["image_key"],
            active_date=data["active_date"]
        )
        
        puzzle = await self.puzzle_repo.create_puzzle(puzzle_create)
        logger.info(f"Created puzzle: {puzzle.id}")
    
    async def validate_character_name(self, name: str, universe: str) -> Dict[str, Any]:
        """Validate a character name against governance rules"""
        validation_result = {
            "name": name,
            "universe": universe,
            "is_valid": True,
            "issues": [],
            "suggestions": []
        }
        
        # Check for duplicates
        duplicates = await self.detect_character_duplicates(name, universe)
        if duplicates:
            validation_result["is_valid"] = False
            validation_result["issues"].append({
                "type": "duplicate_detected",
                "severity": "error",
                "message": f"Found {len(duplicates)} potential duplicates",
                "details": duplicates
            })
        
        # Check name format
        if len(name.strip()) < 2:
            validation_result["is_valid"] = False
            validation_result["issues"].append({
                "type": "invalid_format",
                "severity": "error",
                "message": "Character name must be at least 2 characters long"
            })
        
        # Check for special characters
        if not name.replace(" ", "").replace("-", "").replace(".", "").isalnum():
            validation_result["issues"].append({
                "type": "special_characters",
                "severity": "warning",
                "message": "Character name contains special characters"
            })
        
        return validation_result
    
    async def generate_governance_report(self, report_type: str, filters: Dict[str, Any],
                                       generated_by: str) -> ContentGovernanceReport:
        """Generate a content governance report"""
        report = ContentGovernanceReport(
            report_type=report_type,
            generated_by=generated_by,
            filters=filters
        )
        
        if report_type == "duplicate_analysis":
            await self._generate_duplicate_analysis_report(report, filters)
        elif report_type == "alias_coverage":
            await self._generate_alias_coverage_report(report, filters)
        elif report_type == "content_review_status":
            await self._generate_content_review_status_report(report, filters)
        
        return await self.governance_repo.create_governance_report(report)
    
    async def _generate_duplicate_analysis_report(self, report: ContentGovernanceReport, filters: Dict[str, Any]):
        """Generate duplicate analysis report"""
        universe = filters.get("universe")
        
        # Get all unresolved duplicates
        duplicates = await self.governance_repo.get_duplicate_detections(
            universe=universe,
            resolved=False
        )
        
        # Group by duplicate type
        by_type = {}
        for dup in duplicates:
            if dup.duplicate_type not in by_type:
                by_type[dup.duplicate_type] = []
            by_type[dup.duplicate_type].append(dup)
        
        report.summary = {
            "total_duplicates": len(duplicates),
            "by_type": {k: len(v) for k, v in by_type.items()},
            "high_confidence": len([d for d in duplicates if d.confidence_score > 0.9])
        }
        
        # Add detailed findings
        for dup_type, dup_list in by_type.items():
            report.add_finding({
                "type": "duplicate_group",
                "duplicate_type": dup_type,
                "count": len(dup_list),
                "examples": [d.character_name for d in dup_list[:5]]  # First 5 examples
            })
        
        # Add recommendations
        if report.summary["high_confidence"] > 0:
            report.add_recommendation("Review high-confidence duplicates immediately")
        
        if len(duplicates) > 50:
            report.add_recommendation("Consider implementing automated duplicate resolution for exact matches")
    
    async def _generate_alias_coverage_report(self, report: ContentGovernanceReport, filters: Dict[str, Any]):
        """Generate alias coverage report"""
        universe = filters.get("universe")
        
        characters = await self.governance_repo.get_canonical_characters_by_universe(universe)
        
        total_characters = len(characters)
        characters_with_aliases = len([c for c in characters if c.approved_aliases])
        avg_aliases = sum(len(c.approved_aliases) for c in characters) / total_characters if total_characters > 0 else 0
        
        report.summary = {
            "total_characters": total_characters,
            "characters_with_aliases": characters_with_aliases,
            "coverage_percentage": (characters_with_aliases / total_characters * 100) if total_characters > 0 else 0,
            "average_aliases_per_character": round(avg_aliases, 2)
        }
        
        # Find characters with no aliases
        no_aliases = [c for c in characters if not c.approved_aliases]
        if no_aliases:
            report.add_finding({
                "type": "missing_aliases",
                "count": len(no_aliases),
                "examples": [c.canonical_name for c in no_aliases[:10]]
            })
        
        # Add recommendations
        if report.summary["coverage_percentage"] < 50:
            report.add_recommendation("Improve alias coverage - less than 50% of characters have aliases")
    
    async def _generate_content_review_status_report(self, report: ContentGovernanceReport, filters: Dict[str, Any]):
        """Generate content review status report"""
        # Get review requests by status
        pending = await self.governance_repo.get_content_review_requests(status=ContentStatus.PENDING)
        approved = await self.governance_repo.get_content_review_requests(status=ContentStatus.APPROVED)
        rejected = await self.governance_repo.get_content_review_requests(status=ContentStatus.REJECTED)
        
        report.summary = {
            "pending_reviews": len(pending),
            "approved_reviews": len(approved),
            "rejected_reviews": len(rejected),
            "total_reviews": len(pending) + len(approved) + len(rejected)
        }
        
        # Check for old pending reviews
        old_pending = [r for r in pending if (datetime.utcnow() - r.submitted_at).days > 7]
        if old_pending:
            report.add_finding({
                "type": "stale_reviews",
                "count": len(old_pending),
                "message": "Reviews pending for more than 7 days"
            })
            report.add_recommendation("Review and process stale content review requests")
    
    async def cleanup_resolved_duplicates(self, days_old: int = 30) -> int:
        """Clean up old resolved duplicate detections"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        old_duplicates = await self.governance_repo.get_duplicate_detections(
            resolved=True,
            resolved_before=cutoff_date
        )
        
        deleted_count = 0
        for duplicate in old_duplicates:
            if await self.governance_repo.delete_duplicate_detection(duplicate.id):
                deleted_count += 1
        
        logger.info(f"Cleaned up {deleted_count} old resolved duplicate detections")
        return deleted_count