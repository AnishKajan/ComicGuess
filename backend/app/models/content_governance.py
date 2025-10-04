"""Content governance models for managing character names, aliases, and content review"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Set
from datetime import datetime
from enum import Enum
import uuid
import re


class ContentStatus(str, Enum):
    """Content review status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    NEEDS_REVIEW = "needs_review"


class ContentType(str, Enum):
    """Type of content being reviewed"""
    CHARACTER = "character"
    ALIAS = "alias"
    IMAGE = "image"
    PUZZLE = "puzzle"


class DuplicateType(str, Enum):
    """Type of duplicate detected"""
    EXACT_MATCH = "exact_match"
    SIMILAR_NAME = "similar_name"
    ALIAS_CONFLICT = "alias_conflict"
    PHONETIC_MATCH = "phonetic_match"


class CanonicalCharacter(BaseModel):
    """Canonical character name with approved aliases"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    canonical_name: str = Field(..., description="Official canonical character name")
    universe: str = Field(..., pattern="^(marvel|DC|image)$")
    approved_aliases: List[str] = Field(default_factory=list, description="Approved alternative names")
    rejected_aliases: List[str] = Field(default_factory=list, description="Rejected alternative names")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(..., description="Admin ID who created this entry")
    notes: Optional[str] = None
    
    @field_validator('canonical_name')
    @classmethod
    def validate_canonical_name(cls, v):
        """Validate canonical name format"""
        if not v or not v.strip():
            raise ValueError("Canonical name cannot be empty")
        
        # Basic character name validation
        if len(v.strip()) < 2:
            raise ValueError("Canonical name must be at least 2 characters")
        
        return v.strip()
    
    @field_validator('approved_aliases')
    @classmethod
    def validate_approved_aliases(cls, v):
        """Validate and normalize approved aliases"""
        if not v:
            return []
        
        # Remove duplicates and normalize
        normalized = []
        seen = set()
        
        for alias in v:
            if alias and alias.strip():
                normalized_alias = alias.strip()
                if normalized_alias.lower() not in seen:
                    normalized.append(normalized_alias)
                    seen.add(normalized_alias.lower())
        
        return normalized
    
    def add_alias(self, alias: str) -> bool:
        """Add an alias if it's not already present"""
        if not alias or not alias.strip():
            return False
        
        normalized_alias = alias.strip()
        
        # Check if already in approved or rejected lists
        if (normalized_alias.lower() in [a.lower() for a in self.approved_aliases] or
            normalized_alias.lower() in [a.lower() for a in self.rejected_aliases]):
            return False
        
        self.approved_aliases.append(normalized_alias)
        self.updated_at = datetime.utcnow()
        return True
    
    def reject_alias(self, alias: str) -> bool:
        """Move an alias to rejected list"""
        if not alias or not alias.strip():
            return False
        
        normalized_alias = alias.strip()
        
        # Remove from approved if present
        self.approved_aliases = [a for a in self.approved_aliases if a.lower() != normalized_alias.lower()]
        
        # Add to rejected if not already there
        if normalized_alias.lower() not in [a.lower() for a in self.rejected_aliases]:
            self.rejected_aliases.append(normalized_alias)
            self.updated_at = datetime.utcnow()
            return True
        
        return False
    
    def get_all_names(self) -> List[str]:
        """Get all valid names (canonical + approved aliases)"""
        return [self.canonical_name] + self.approved_aliases


class DuplicateDetection(BaseModel):
    """Duplicate detection result"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    character_name: str = Field(...)
    universe: str = Field(...)
    duplicate_type: DuplicateType = Field(...)
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    existing_character_id: Optional[str] = None
    existing_character_name: Optional[str] = None
    suggested_action: str = Field(..., description="Suggested action to resolve duplicate")
    details: Dict[str, Any] = Field(default_factory=dict)
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved: bool = Field(default=False)
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


class ContentReviewRequest(BaseModel):
    """Content review request"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content_type: ContentType = Field(...)
    content_data: Dict[str, Any] = Field(..., description="Content data to be reviewed")
    submitted_by: str = Field(..., description="User/admin ID who submitted")
    submitted_at: datetime = Field(default_factory=datetime.utcnow)
    status: ContentStatus = Field(default=ContentStatus.PENDING)
    priority: int = Field(default=1, ge=1, le=5, description="Priority 1-5, 5 being highest")
    
    # Review information
    reviewer_id: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    
    # Approval workflow
    requires_approval: bool = Field(default=True)
    approval_threshold: int = Field(default=1, description="Number of approvals needed")
    approvals: List[str] = Field(default_factory=list, description="List of admin IDs who approved")
    rejections: List[str] = Field(default_factory=list, description="List of admin IDs who rejected")
    
    def add_approval(self, admin_id: str) -> bool:
        """Add approval from an admin"""
        if admin_id not in self.approvals and admin_id not in self.rejections:
            self.approvals.append(admin_id)
            
            # Check if we have enough approvals
            if len(self.approvals) >= self.approval_threshold:
                self.status = ContentStatus.APPROVED
                self.reviewed_at = datetime.utcnow()
            
            return True
        return False
    
    def add_rejection(self, admin_id: str, notes: Optional[str] = None) -> bool:
        """Add rejection from an admin"""
        if admin_id not in self.rejections and admin_id not in self.approvals:
            self.rejections.append(admin_id)
            self.status = ContentStatus.REJECTED
            self.reviewed_at = datetime.utcnow()
            if notes:
                self.review_notes = notes
            return True
        return False
    
    def is_approved(self) -> bool:
        """Check if content is approved"""
        return self.status == ContentStatus.APPROVED
    
    def is_rejected(self) -> bool:
        """Check if content is rejected"""
        return self.status == ContentStatus.REJECTED


class LocaleAwareNameMatcher(BaseModel):
    """Locale-aware character name matching system"""
    
    @staticmethod
    def normalize_name(name: str) -> str:
        """Normalize a character name for comparison"""
        if not name:
            return ""
        
        # Convert to lowercase
        normalized = name.lower().strip()
        
        # Remove common prefixes/suffixes
        prefixes = ["the ", "dr. ", "mr. ", "ms. ", "captain ", "professor "]
        suffixes = [" jr.", " sr.", " ii", " iii", " iv"]
        
        for prefix in prefixes:
            if normalized.startswith(prefix):
                normalized = normalized[len(prefix):]
                break
        
        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]
                break
        
        # Remove special characters but keep spaces and hyphens
        normalized = re.sub(r'[^\w\s\-]', '', normalized)
        
        # Normalize whitespace
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    @staticmethod
    def calculate_similarity(name1: str, name2: str) -> float:
        """Calculate similarity between two names (0-1)"""
        if not name1 or not name2:
            return 0.0
        
        norm1 = LocaleAwareNameMatcher.normalize_name(name1)
        norm2 = LocaleAwareNameMatcher.normalize_name(name2)
        
        if norm1 == norm2:
            return 1.0
        
        # Simple Levenshtein distance-based similarity
        def levenshtein_distance(s1: str, s2: str) -> int:
            if len(s1) < len(s2):
                return levenshtein_distance(s2, s1)
            
            if len(s2) == 0:
                return len(s1)
            
            previous_row = list(range(len(s2) + 1))
            for i, c1 in enumerate(s1):
                current_row = [i + 1]
                for j, c2 in enumerate(s2):
                    insertions = previous_row[j + 1] + 1
                    deletions = current_row[j] + 1
                    substitutions = previous_row[j] + (c1 != c2)
                    current_row.append(min(insertions, deletions, substitutions))
                previous_row = current_row
            
            return previous_row[-1]
        
        max_len = max(len(norm1), len(norm2))
        if max_len == 0:
            return 1.0
        
        distance = levenshtein_distance(norm1, norm2)
        similarity = 1.0 - (distance / max_len)
        
        return max(0.0, similarity)
    
    @staticmethod
    def is_phonetic_match(name1: str, name2: str) -> bool:
        """Check if two names are phonetically similar"""
        # Simple phonetic matching - could be enhanced with Soundex or Metaphone
        norm1 = LocaleAwareNameMatcher.normalize_name(name1)
        norm2 = LocaleAwareNameMatcher.normalize_name(name2)
        
        # Remove vowels for basic phonetic comparison
        consonants1 = re.sub(r'[aeiou]', '', norm1)
        consonants2 = re.sub(r'[aeiou]', '', norm2)
        
        return consonants1 == consonants2 and len(consonants1) > 2
    
    @staticmethod
    def find_potential_duplicates(name: str, existing_names: List[str], 
                                similarity_threshold: float = 0.8) -> List[Dict[str, Any]]:
        """Find potential duplicates for a given name"""
        duplicates = []
        
        for existing_name in existing_names:
            similarity = LocaleAwareNameMatcher.calculate_similarity(name, existing_name)
            
            if similarity >= similarity_threshold:
                duplicate_type = DuplicateType.EXACT_MATCH if similarity == 1.0 else DuplicateType.SIMILAR_NAME
                
                duplicates.append({
                    "name": existing_name,
                    "similarity": similarity,
                    "type": duplicate_type
                })
            elif LocaleAwareNameMatcher.is_phonetic_match(name, existing_name):
                duplicates.append({
                    "name": existing_name,
                    "similarity": 0.7,  # Default phonetic similarity
                    "type": DuplicateType.PHONETIC_MATCH
                })
        
        # Sort by similarity score descending
        duplicates.sort(key=lambda x: x["similarity"], reverse=True)
        
        return duplicates


class ContentGovernanceRule(BaseModel):
    """Content governance rule definition"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., description="Rule name")
    description: str = Field(..., description="Rule description")
    rule_type: str = Field(..., description="Type of rule (validation, approval, etc.)")
    universe: Optional[str] = Field(None, pattern="^(marvel|DC|image|all)$")
    is_active: bool = Field(default=True)
    severity: str = Field(default="warning", pattern="^(info|warning|error|critical)$")
    
    # Rule configuration
    config: Dict[str, Any] = Field(default_factory=dict)
    
    # Metadata
    created_by: str = Field(...)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def validate_content(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Validate content against this rule"""
        # This would contain rule-specific validation logic
        # For now, return a basic structure
        return {
            "rule_id": self.id,
            "rule_name": self.name,
            "passed": True,
            "severity": self.severity,
            "message": "Content passed validation",
            "details": {}
        }


class ContentGovernanceReport(BaseModel):
    """Content governance report"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    report_type: str = Field(..., description="Type of report")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    generated_by: str = Field(..., description="Admin ID who generated report")
    
    # Report data
    summary: Dict[str, Any] = Field(default_factory=dict)
    details: List[Dict[str, Any]] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # Filters used
    filters: Dict[str, Any] = Field(default_factory=dict)
    
    def add_finding(self, finding: Dict[str, Any]):
        """Add a finding to the report"""
        self.details.append({
            **finding,
            "timestamp": datetime.utcnow().isoformat()
        })
    
    def add_recommendation(self, recommendation: str):
        """Add a recommendation to the report"""
        if recommendation not in self.recommendations:
            self.recommendations.append(recommendation)