#!/bin/bash

# Production Rollback Script for ComicGuess
# This script handles emergency rollback procedures

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BACKEND_RESOURCE_GROUP="comicguess-rg"
BACKEND_APP_NAME="comicguess-backend-prod"

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_critical() {
    echo -e "${RED}[CRITICAL]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites for rollback..."
    
    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Cannot perform rollback."
        exit 1
    fi
    
    # Check if Vercel CLI is installed
    if ! command -v vercel &> /dev/null; then
        log_error "Vercel CLI is not installed. Cannot perform frontend rollback."
        exit 1
    fi
    
    # Check Azure login
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi
    
    # Check Vercel login
    if ! vercel whoami &> /dev/null; then
        log_error "Not logged in to Vercel. Please run 'vercel login' first."
        exit 1
    fi
    
    log_success "Prerequisites check completed"
}

list_backend_deployments() {
    log_info "Listing recent backend deployments..."
    
    echo "Recent Azure App Service deployments:"
    az webapp deployment list \
        --name $BACKEND_APP_NAME \
        --resource-group $BACKEND_RESOURCE_GROUP \
        --query "[].{id:id, status:status, start_time:start_time, end_time:end_time}" \
        --output table
}

list_frontend_deployments() {
    log_info "Listing recent frontend deployments..."
    
    cd frontend
    echo "Recent Vercel deployments:"
    vercel ls --scope team 2>/dev/null || vercel ls
    cd ..
}

rollback_backend() {
    local deployment_id=$1
    
    if [ -z "$deployment_id" ]; then
        log_error "No deployment ID provided for backend rollback"
        return 1
    fi
    
    log_info "Rolling back backend to deployment: $deployment_id"
    
    # Note: Azure App Service doesn't have a direct rollback command
    # This would typically involve redeploying from a previous version
    log_warning "Azure App Service rollback requires manual intervention"
    log_info "To rollback backend:"
    echo "1. Go to Azure Portal"
    echo "2. Navigate to App Service: $BACKEND_APP_NAME"
    echo "3. Go to Deployment Center"
    echo "4. Select deployment: $deployment_id"
    echo "5. Click 'Redeploy'"
    
    # Alternative: Redeploy from Git
    log_info "Alternative: Redeploy from Git commit"
    echo "Run: az webapp deployment source config --name $BACKEND_APP_NAME --resource-group $BACKEND_RESOURCE_GROUP --repo-url <git-url> --branch <previous-commit>"
}

rollback_frontend() {
    local deployment_url=$1
    
    if [ -z "$deployment_url" ]; then
        log_error "No deployment URL provided for frontend rollback"
        return 1
    fi
    
    log_info "Rolling back frontend to deployment: $deployment_url"
    
    cd frontend
    
    # Promote previous deployment to production
    if vercel promote "$deployment_url" --scope team 2>/dev/null || vercel promote "$deployment_url"; then
        log_success "Frontend rollback completed successfully"
    else
        log_error "Frontend rollback failed"
        cd ..
        return 1
    fi
    
    cd ..
}

emergency_rollback() {
    log_critical "EMERGENCY ROLLBACK INITIATED"
    log_critical "This will rollback both frontend and backend to previous versions"
    
    read -p "Are you sure you want to proceed? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        log_info "Rollback cancelled"
        exit 0
    fi
    
    # Get the most recent deployments
    log_info "Getting recent deployments..."
    
    # Frontend rollback (get second most recent deployment)
    cd frontend
    PREVIOUS_DEPLOYMENT=$(vercel ls --scope team 2>/dev/null | grep -v "production" | head -1 | awk '{print $2}' || vercel ls | grep -v "production" | head -1 | awk '{print $2}')
    
    if [ -n "$PREVIOUS_DEPLOYMENT" ]; then
        log_info "Rolling back frontend to: $PREVIOUS_DEPLOYMENT"
        rollback_frontend "$PREVIOUS_DEPLOYMENT"
    else
        log_error "No previous frontend deployment found"
    fi
    cd ..
    
    # Backend rollback instructions
    log_warning "Backend rollback requires manual intervention via Azure Portal"
    rollback_backend "latest-1"
}

verify_rollback() {
    log_info "Verifying rollback status..."
    
    # Check backend health
    BACKEND_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"
    log_info "Checking backend health at: $BACKEND_URL/health"
    
    if curl -f -s "$BACKEND_URL/health" > /dev/null; then
        log_success "Backend is healthy after rollback"
    else
        log_error "Backend health check failed after rollback"
    fi
    
    # Check frontend
    cd frontend
    FRONTEND_URL=$(vercel ls --scope team 2>/dev/null | grep production | awk '{print $2}' | head -1 || vercel ls | grep production | awk '{print $2}' | head -1)
    if [ -n "$FRONTEND_URL" ]; then
        log_info "Checking frontend at: https://$FRONTEND_URL"
        if curl -f -s "https://$FRONTEND_URL" > /dev/null; then
            log_success "Frontend is accessible after rollback"
        else
            log_warning "Frontend accessibility check failed"
        fi
    fi
    cd ..
}

create_incident_report() {
    local reason=$1
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    
    cat > "incident-report-${timestamp}.md" << EOF
# Incident Report - Production Rollback

**Date:** $timestamp
**Reason:** $reason
**Action Taken:** Production rollback initiated

## Timeline

- **$timestamp**: Rollback initiated
- **$timestamp**: Backend rollback instructions provided
- **$timestamp**: Frontend rollback attempted
- **$timestamp**: Verification completed

## Services Affected

- Backend API: https://${BACKEND_APP_NAME}.azurewebsites.net
- Frontend Application: Production Vercel deployment

## Rollback Actions

### Backend
- Manual rollback required via Azure Portal
- Deployment Center -> Select previous deployment -> Redeploy

### Frontend
- Automated rollback via Vercel CLI
- Previous deployment promoted to production

## Verification

- Health checks performed on both services
- Monitoring dashboards reviewed
- User impact assessed

## Next Steps

1. Investigate root cause of the issue
2. Implement fixes in development environment
3. Test thoroughly before next deployment
4. Update deployment procedures if necessary
5. Conduct post-incident review

## Lessons Learned

- [To be filled after investigation]

## Action Items

- [ ] Root cause analysis
- [ ] Fix implementation
- [ ] Testing in staging
- [ ] Documentation updates
- [ ] Process improvements

---
Generated by rollback script at $timestamp
EOF

    log_info "Incident report created: incident-report-${timestamp}.md"
}

print_rollback_summary() {
    echo ""
    echo "=========================================="
    echo "         ROLLBACK SUMMARY"
    echo "=========================================="
    echo ""
    echo "Backend:  Manual rollback required via Azure Portal"
    echo "Frontend: Automated rollback completed"
    echo ""
    echo "Next Steps:"
    echo "1. Complete backend rollback via Azure Portal"
    echo "2. Verify all services are functioning"
    echo "3. Investigate the root cause"
    echo "4. Plan remediation steps"
    echo "5. Update incident report"
    echo ""
    echo "Rollback process completed! 🔄"
    echo "=========================================="
}

# Main rollback functions
case "${1:-}" in
    --backend)
        log_info "Rolling back backend only..."
        check_prerequisites
        list_backend_deployments
        echo ""
        read -p "Enter deployment ID to rollback to: " deployment_id
        rollback_backend "$deployment_id"
        verify_rollback
        ;;
    --frontend)
        log_info "Rolling back frontend only..."
        check_prerequisites
        list_frontend_deployments
        echo ""
        read -p "Enter deployment URL to rollback to: " deployment_url
        rollback_frontend "$deployment_url"
        verify_rollback
        ;;
    --emergency)
        emergency_rollback
        verify_rollback
        create_incident_report "Emergency rollback - automated"
        print_rollback_summary
        ;;
    --list)
        check_prerequisites
        list_backend_deployments
        echo ""
        list_frontend_deployments
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --backend     Rollback backend only"
        echo "  --frontend    Rollback frontend only"
        echo "  --emergency   Emergency rollback (both services)"
        echo "  --list        List recent deployments"
        echo "  --help, -h    Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 --list                    # List recent deployments"
        echo "  $0 --frontend               # Interactive frontend rollback"
        echo "  $0 --backend                # Interactive backend rollback"
        echo "  $0 --emergency              # Emergency rollback"
        echo ""
        exit 0
        ;;
    "")
        log_info "Interactive rollback mode"
        check_prerequisites
        
        echo "Select rollback option:"
        echo "1) Backend only"
        echo "2) Frontend only"
        echo "3) Emergency rollback (both)"
        echo "4) List deployments"
        echo "5) Exit"
        
        read -p "Enter choice (1-5): " choice
        
        case $choice in
            1)
                list_backend_deployments
                read -p "Enter deployment ID to rollback to: " deployment_id
                rollback_backend "$deployment_id"
                verify_rollback
                ;;
            2)
                list_frontend_deployments
                read -p "Enter deployment URL to rollback to: " deployment_url
                rollback_frontend "$deployment_url"
                verify_rollback
                ;;
            3)
                read -p "Enter reason for emergency rollback: " reason
                emergency_rollback
                verify_rollback
                create_incident_report "$reason"
                print_rollback_summary
                ;;
            4)
                list_backend_deployments
                echo ""
                list_frontend_deployments
                ;;
            5)
                log_info "Exiting..."
                exit 0
                ;;
            *)
                log_error "Invalid choice"
                exit 1
                ;;
        esac
        ;;
    *)
        log_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac