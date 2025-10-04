"""
Attribution models for intellectual property compliance.
Handles character attribution, copyright notices, and licensing information.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum

class RightsHolder(str, Enum):
    """Enumeration of comic book rights holders"""
    MARVEL = "Marvel Comics"
    DC = "DC Comics" 
    IMAGE = "Image Comics"
    DARK_HORSE = "Dark Horse Comics"
    IDW = "IDW Publishing"
    VALIANT = "Valiant Entertainment"
    DYNAMITE = "Dynamite Entertainment"
    OTHER = "Other"

class LicenseType(str, Enum):
    """Types of licensing arrangements"""
    FAIR_USE = "fair_use"
    LICENSED = "licensed"
    PUBLIC_DOMAIN = "public_domain"
    CREATOR_PERMISSION = "creator_permission"

class Attribution(BaseModel):
    """Attribution information for character content"""
    
    character_name: str = Field(..., description="Name of the character")
    rights_holder: RightsHolder = Field(..., description="Primary rights holder")
    copyright_notice: str = Field(..., description="Copyright notice text")
    license_type: LicenseType = Field(default=LicenseType.FAIR_USE, description="Type of license or usage")
    attribution_text: str = Field(..., description="Full attribution text for display")
    
    # Optional fields for detailed tracking
    creator_names: Optional[str] = Field(None, description="Original creator names")
    first_appearance: Optional[str] = Field(None, description="First comic appearance")
    trademark_info: Optional[str] = Field(None, description="Trademark information")
    
    # Image-specific attribution
    image_source: Optional[str] = Field(None, description="Source of character image")
    image_copyright: Optional[str] = Field(None, description="Image copyright holder")
    image_license: Optional[str] = Field(None, description="Image license terms")
    
    # Compliance tracking
    legal_review_date: Optional[datetime] = Field(None, description="Date of legal review")
    compliance_notes: Optional[str] = Field(None, description="Compliance notes")
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = Field(None)

class AttributionDisplay(BaseModel):
    """Formatted attribution for frontend display"""
    
    character_name: str
    short_attribution: str = Field(..., description="Brief attribution for UI")
    full_attribution: str = Field(..., description="Complete attribution text")
    copyright_notice: str
    fair_use_disclaimer: str = Field(..., description="Fair use disclaimer text")
    
    @classmethod
    def from_attribution(cls, attribution: Attribution) -> "AttributionDisplay":
        """Create display attribution from full attribution model"""
        
        # Generate short attribution for UI
        short_attribution = f"© {attribution.rights_holder.value}"
        
        # Generate full attribution text
        full_attribution_parts = [
            f"Character: {attribution.character_name}",
            f"© {attribution.rights_holder.value}"
        ]
        
        if attribution.creator_names:
            full_attribution_parts.append(f"Created by: {attribution.creator_names}")
        
        if attribution.first_appearance:
            full_attribution_parts.append(f"First appeared in: {attribution.first_appearance}")
        
        full_attribution = " | ".join(full_attribution_parts)
        
        # Fair use disclaimer
        fair_use_disclaimer = (
            "Character name and image used under fair use for educational and "
            "entertainment purposes. All rights belong to their respective owners."
        )
        
        return cls(
            character_name=attribution.character_name,
            short_attribution=short_attribution,
            full_attribution=full_attribution,
            copyright_notice=attribution.copyright_notice,
            fair_use_disclaimer=fair_use_disclaimer
        )

class IPComplianceReport(BaseModel):
    """Report on IP compliance status"""
    
    total_characters: int
    attributed_characters: int
    missing_attribution: int
    
    rights_holder_breakdown: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of characters by rights holder"
    )
    
    license_type_breakdown: Dict[str, int] = Field(
        default_factory=dict, 
        description="Count of characters by license type"
    )
    
    compliance_issues: list[str] = Field(
        default_factory=list,
        description="List of compliance issues found"
    )
    
    last_review_date: Optional[datetime] = Field(None)
    generated_at: datetime = Field(default_factory=datetime.utcnow)

class TakedownRequest(BaseModel):
    """Model for handling IP takedown requests"""
    
    id: str = Field(..., description="Unique request ID")
    character_name: str = Field(..., description="Character subject to takedown")
    rights_holder: str = Field(..., description="Entity requesting takedown")
    
    request_type: str = Field(..., description="Type of request (DMCA, cease and desist, etc.)")
    request_details: str = Field(..., description="Details of the request")
    
    contact_email: str = Field(..., description="Contact email for requester")
    contact_name: Optional[str] = Field(None, description="Contact name")
    
    # Request processing
    status: str = Field(default="pending", description="Request status")
    received_at: datetime = Field(default_factory=datetime.utcnow)
    processed_at: Optional[datetime] = Field(None)
    response_sent_at: Optional[datetime] = Field(None)
    
    # Actions taken
    content_removed: bool = Field(default=False)
    removal_date: Optional[datetime] = Field(None)
    
    # Internal notes
    internal_notes: Optional[str] = Field(None)
    legal_review_required: bool = Field(default=True)

def generate_standard_attribution(
    character_name: str,
    rights_holder: RightsHolder,
    creator_names: Optional[str] = None,
    first_appearance: Optional[str] = None
) -> Attribution:
    """Generate standard attribution for a character"""
    
    # Generate copyright notice
    current_year = datetime.now().year
    copyright_notice = f"© {current_year} {rights_holder.value}. All rights reserved."
    
    # Generate attribution text
    attribution_parts = [
        f"{character_name} is a trademark and copyright of {rights_holder.value}."
    ]
    
    if creator_names:
        attribution_parts.append(f"Created by {creator_names}.")
    
    if first_appearance:
        attribution_parts.append(f"First appeared in {first_appearance}.")
    
    attribution_parts.append(
        "Used under fair use for educational and entertainment purposes."
    )
    
    attribution_text = " ".join(attribution_parts)
    
    return Attribution(
        character_name=character_name,
        rights_holder=rights_holder,
        copyright_notice=copyright_notice,
        license_type=LicenseType.FAIR_USE,
        attribution_text=attribution_text,
        creator_names=creator_names,
        first_appearance=first_appearance
    )

def get_rights_holder_from_universe(universe: str) -> RightsHolder:
    """Get rights holder based on universe"""
    universe_mapping = {
        "marvel": RightsHolder.MARVEL,
        "DC": RightsHolder.DC,
        "image": RightsHolder.IMAGE
    }
    
    return universe_mapping.get(universe.lower(), RightsHolder.OTHER)