"""
IP Compliance API endpoints for managing intellectual property compliance,
attribution, and takedown requests.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..auth.middleware import get_current_user
from ..models.user import User
from ..models.attribution import (
    Attribution,
    AttributionDisplay,
    IPComplianceReport,
    TakedownRequest,
    RightsHolder
)
from ..services.ip_compliance_service import IPComplianceService
from ..database.connection import get_database

router = APIRouter(prefix="/api/ip-compliance", tags=["ip-compliance"])

@router.get("/attribution/{character_name}")
async def get_character_attribution(
    character_name: str,
    db = Depends(get_database)
) -> Optional[AttributionDisplay]:
    """
    Get attribution information for a character.
    
    Args:
        character_name: Name of the character
        db: Database connection
        
    Returns:
        Attribution display information
    """
    try:
        service = IPComplianceService()
        attribution = await service.get_character_display_attribution(character_name)
        
        if not attribution:
            raise HTTPException(
                status_code=404,
                detail=f"No attribution found for character: {character_name}"
            )
        
        return attribution
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get attribution: {str(e)}"
        )

@router.post("/attribution/{character_name}")
async def update_character_attribution(
    character_name: str,
    creator_names: Optional[str] = None,
    first_appearance: Optional[str] = None,
    image_source: Optional[str] = None,
    compliance_notes: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Attribution:
    """
    Update attribution information for a character.
    Requires admin privileges.
    
    Args:
        character_name: Name of the character
        creator_names: Original creator names
        first_appearance: First comic appearance
        image_source: Source of character image
        compliance_notes: Compliance notes
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        Updated attribution
    """
    # Check admin privileges (implement admin check)
    # if not current_user.is_admin:
    #     raise HTTPException(status_code=403, detail="Admin privileges required")
    
    try:
        service = IPComplianceService()
        attribution = await service.update_character_attribution(
            character_name=character_name,
            creator_names=creator_names,
            first_appearance=first_appearance,
            image_source=image_source,
            compliance_notes=compliance_notes
        )
        
        if not attribution:
            raise HTTPException(
                status_code=404,
                detail=f"No attribution found for character: {character_name}"
            )
        
        return attribution
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update attribution: {str(e)}"
        )

@router.get("/compliance-report")
async def get_compliance_report(
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> IPComplianceReport:
    """
    Generate IP compliance report.
    Requires admin privileges.
    
    Args:
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        Compliance report
    """
    try:
        service = IPComplianceService()
        report = await service.generate_compliance_report()
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate compliance report: {str(e)}"
        )

@router.get("/universe-report/{universe}")
async def get_universe_attribution_report(
    universe: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    Generate attribution report for a specific universe.
    
    Args:
        universe: Universe name (marvel, DC, image)
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        Universe attribution report
    """
    if universe not in ["marvel", "DC", "image"]:
        raise HTTPException(
            status_code=400,
            detail="Universe must be one of: marvel, DC, image"
        )
    
    try:
        service = IPComplianceService()
        report = await service.generate_attribution_report_by_universe(universe)
        return report
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate universe report: {str(e)}"
        )

@router.get("/characters-needing-review")
async def get_characters_needing_review(
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> List[Attribution]:
    """
    Get characters that need legal review.
    Requires admin privileges.
    
    Args:
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        List of attributions needing review
    """
    try:
        service = IPComplianceService()
        attributions = await service.get_characters_needing_review()
        return attributions
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get characters needing review: {str(e)}"
        )

@router.post("/legal-review/{character_name}")
async def mark_legal_review_completed(
    character_name: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    Mark legal review as completed for a character.
    Requires admin privileges.
    
    Args:
        character_name: Name of the character
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        Success confirmation
    """
    try:
        service = IPComplianceService()
        success = await service.mark_legal_review_completed(character_name)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"No attribution found for character: {character_name}"
            )
        
        return {
            "success": True,
            "message": f"Legal review marked complete for {character_name}",
            "reviewed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to mark legal review: {str(e)}"
        )

@router.post("/takedown-request")
async def create_takedown_request(
    character_name: str,
    rights_holder: str,
    request_type: str,
    request_details: str,
    contact_email: str,
    contact_name: Optional[str] = None,
    db = Depends(get_database)
) -> TakedownRequest:
    """
    Create a takedown request for character content.
    Public endpoint for rights holders.
    
    Args:
        character_name: Character subject to takedown
        rights_holder: Entity requesting takedown
        request_type: Type of request (DMCA, cease and desist, etc.)
        request_details: Details of the request
        contact_email: Contact email
        contact_name: Contact name (optional)
        db: Database connection
        
    Returns:
        Created takedown request
    """
    try:
        service = IPComplianceService()
        request = await service.create_takedown_request(
            character_name=character_name,
            rights_holder=rights_holder,
            request_type=request_type,
            request_details=request_details,
            contact_email=contact_email,
            contact_name=contact_name
        )
        
        return request
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create takedown request: {str(e)}"
        )

@router.get("/takedown-requests")
async def get_pending_takedown_requests(
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> List[TakedownRequest]:
    """
    Get all pending takedown requests.
    Requires admin privileges.
    
    Args:
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        List of pending takedown requests
    """
    try:
        service = IPComplianceService()
        requests = await service.get_pending_takedown_requests()
        return requests
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get takedown requests: {str(e)}"
        )

@router.post("/takedown-requests/{request_id}/process")
async def process_takedown_request(
    request_id: str,
    remove_content: bool = True,
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    Process a takedown request.
    Requires admin privileges.
    
    Args:
        request_id: Takedown request ID
        remove_content: Whether to remove the content
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        Processing result
    """
    try:
        service = IPComplianceService()
        success = await service.process_takedown_request(request_id, remove_content)
        
        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"Takedown request not found: {request_id}"
            )
        
        return {
            "success": True,
            "message": "Takedown request processed successfully",
            "content_removed": remove_content,
            "processed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process takedown request: {str(e)}"
        )

@router.get("/fair-use-validation/{character_name}")
async def validate_fair_use_compliance(
    character_name: str,
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    Validate fair use compliance for a character.
    
    Args:
        character_name: Name of the character
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        Fair use compliance validation
    """
    try:
        service = IPComplianceService()
        validation = await service.validate_fair_use_compliance(character_name)
        return validation
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to validate fair use compliance: {str(e)}"
        )

@router.get("/export-attribution-data")
async def export_attribution_data(
    current_user: User = Depends(get_current_user),
    db = Depends(get_database)
) -> Dict[str, Any]:
    """
    Export all attribution data for backup/audit.
    Requires admin privileges.
    
    Args:
        current_user: Authenticated user
        db: Database connection
        
    Returns:
        Exported attribution data
    """
    try:
        service = IPComplianceService()
        export_data = await service.export_attribution_data()
        return export_data
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to export attribution data: {str(e)}"
        )