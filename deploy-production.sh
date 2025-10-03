#!/bin/bash

# Production Deployment Script for ComicGuess
# This script handles the complete production deployment process

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
FRONTEND_PROJECT_NAME="comicguess-frontend"
AZURE_LOCATION="eastus"

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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if Azure CLI is installed
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Vercel CLI is installed
    if ! command -v vercel &> /dev/null; then
        log_error "Vercel CLI is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Node.js is installed
    if ! command -v node &> /dev/null; then
        log_error "Node.js is not installed. Please install it first."
        exit 1
    fi
    
    # Check if Python is installed
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 is not installed. Please install it first."
        exit 1
    fi
    
    log_success "All prerequisites are installed"
}

run_security_audit() {
    log_info "Running security audit..."
    
    if node security-audit.js; then
        log_success "Security audit passed"
    else
        log_error "Security audit failed. Please fix security issues before deployment."
        exit 1
    fi
}

run_tests() {
    log_info "Running tests..."
    
    # Backend tests
    log_info "Running backend tests..."
    cd backend
    if python -m pytest tests/ -v --tb=short; then
        log_success "Backend tests passed"
    else
        log_error "Backend tests failed"
        cd ..
        exit 1
    fi
    cd ..
    
    # Frontend tests
    log_info "Running frontend tests..."
    cd frontend
    if npm test -- --run; then
        log_success "Frontend tests passed"
    else
        log_error "Frontend tests failed"
        cd ..
        exit 1
    fi
    cd ..
}

run_integration_tests() {
    log_info "Running integration tests..."
    
    if node integration-test.js; then
        log_success "Integration tests passed"
    else
        log_error "Integration tests failed"
        exit 1
    fi
}

deploy_backend() {
    log_info "Deploying backend to Azure App Service..."
    
    cd backend
    
    # Check if logged in to Azure
    if ! az account show &> /dev/null; then
        log_error "Not logged in to Azure. Please run 'az login' first."
        exit 1
    fi
    
    # Create resource group if it doesn't exist
    if ! az group show --name $BACKEND_RESOURCE_GROUP &> /dev/null; then
        log_info "Creating resource group: $BACKEND_RESOURCE_GROUP"
        az group create --name $BACKEND_RESOURCE_GROUP --location $AZURE_LOCATION
    fi
    
    # Deploy using Azure CLI
    log_info "Deploying backend application..."
    az webapp up \
        --name $BACKEND_APP_NAME \
        --resource-group $BACKEND_RESOURCE_GROUP \
        --location $AZURE_LOCATION \
        --runtime "PYTHON:3.11" \
        --sku B1
    
    # Configure startup command
    az webapp config set \
        --name $BACKEND_APP_NAME \
        --resource-group $BACKEND_RESOURCE_GROUP \
        --startup-file "uvicorn main:app --host 0.0.0.0 --port 8000"
    
    # Set environment variables
    log_info "Configuring environment variables..."
    az webapp config appsettings set \
        --name $BACKEND_APP_NAME \
        --resource-group $BACKEND_RESOURCE_GROUP \
        --settings \
            APP_ENV=production \
            DEBUG=false \
            LOG_LEVEL=INFO \
            WEBSITES_PORT=8000 \
            SCM_DO_BUILD_DURING_DEPLOYMENT=true \
            ENABLE_ORYX_BUILD=true
    
    # Get the backend URL
    BACKEND_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"
    log_success "Backend deployed successfully to: $BACKEND_URL"
    
    cd ..
}

deploy_frontend() {
    log_info "Deploying frontend to Vercel..."
    
    cd frontend
    
    # Check if logged in to Vercel
    if ! vercel whoami &> /dev/null; then
        log_error "Not logged in to Vercel. Please run 'vercel login' first."
        exit 1
    fi
    
    # Set environment variables for production
    export NEXT_PUBLIC_API_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"
    export NEXT_PUBLIC_APP_ENV="production"
    
    # Deploy to production
    log_info "Deploying frontend application..."
    vercel --prod --yes
    
    log_success "Frontend deployed successfully"
    
    cd ..
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Wait a moment for services to start
    sleep 10
    
    # Check backend health
    BACKEND_URL="https://${BACKEND_APP_NAME}.azurewebsites.net"
    log_info "Checking backend health at: $BACKEND_URL/health"
    
    if curl -f -s "$BACKEND_URL/health" > /dev/null; then
        log_success "Backend is healthy"
    else
        log_error "Backend health check failed"
        exit 1
    fi
    
    # Check frontend (get URL from Vercel)
    FRONTEND_URL=$(cd frontend && vercel ls --scope team 2>/dev/null | grep production | awk '{print $2}' | head -1)
    if [ -n "$FRONTEND_URL" ]; then
        log_info "Checking frontend at: https://$FRONTEND_URL"
        if curl -f -s "https://$FRONTEND_URL" > /dev/null; then
            log_success "Frontend is accessible"
        else
            log_warning "Frontend accessibility check failed (may be normal during deployment)"
        fi
    fi
}

setup_monitoring() {
    log_info "Setting up monitoring and alerts..."
    
    # This would typically involve:
    # - Configuring Application Insights
    # - Setting up log analytics
    # - Creating alert rules
    # - Configuring dashboards
    
    log_info "Monitoring setup would be configured here"
    log_warning "Please manually configure Application Insights and monitoring dashboards"
}

cleanup() {
    log_info "Cleaning up temporary files..."
    
    # Remove any temporary files created during deployment
    rm -f security-audit-report.json
    
    log_success "Cleanup completed"
}

print_summary() {
    echo ""
    echo "=========================================="
    echo "         DEPLOYMENT SUMMARY"
    echo "=========================================="
    echo ""
    echo "Backend URL:  https://${BACKEND_APP_NAME}.azurewebsites.net"
    echo "Frontend URL: Check Vercel dashboard for production URL"
    echo ""
    echo "Next Steps:"
    echo "1. Configure custom domain in Cloudflare"
    echo "2. Set up SSL certificates"
    echo "3. Configure monitoring dashboards"
    echo "4. Set up backup procedures"
    echo "5. Configure alerting rules"
    echo ""
    echo "Deployment completed successfully! 🚀"
    echo "=========================================="
}

# Main deployment process
main() {
    log_info "Starting ComicGuess production deployment..."
    
    check_prerequisites
    run_security_audit
    run_tests
    
    # Only run integration tests if services are already running
    if curl -f -s "http://localhost:8000/health" > /dev/null 2>&1; then
        run_integration_tests
    else
        log_warning "Skipping integration tests (services not running locally)"
    fi
    
    deploy_backend
    deploy_frontend
    verify_deployment
    setup_monitoring
    cleanup
    print_summary
}

# Handle script arguments
case "${1:-}" in
    --backend-only)
        log_info "Deploying backend only..."
        check_prerequisites
        run_security_audit
        deploy_backend
        verify_deployment
        ;;
    --frontend-only)
        log_info "Deploying frontend only..."
        check_prerequisites
        deploy_frontend
        verify_deployment
        ;;
    --skip-tests)
        log_info "Skipping tests..."
        check_prerequisites
        run_security_audit
        deploy_backend
        deploy_frontend
        verify_deployment
        setup_monitoring
        cleanup
        print_summary
        ;;
    --help|-h)
        echo "Usage: $0 [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --backend-only   Deploy only the backend"
        echo "  --frontend-only  Deploy only the frontend"
        echo "  --skip-tests     Skip running tests"
        echo "  --help, -h       Show this help message"
        echo ""
        exit 0
        ;;
    "")
        main
        ;;
    *)
        log_error "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
esac