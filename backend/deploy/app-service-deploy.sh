#!/bin/bash

# Azure App Service Deployment Script
# This script deploys the ComicGuess backend to Azure App Service

set -e  # Exit on any error

# Configuration
RESOURCE_GROUP="comicguess-rg"
APP_NAME="comicguess-backend"
LOCATION="eastus"
SKU="B1"
RUNTIME="PYTHON:3.11"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    error "Azure CLI is not installed. Please install it first."
fi

# Check if logged in to Azure
if ! az account show &> /dev/null; then
    error "Not logged in to Azure. Please run 'az login' first."
fi

# Parse command line arguments
ENVIRONMENT="staging"
DEPLOY_TYPE="code"

while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --type)
            DEPLOY_TYPE="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [--env staging|production] [--type code|docker]"
            echo "  --env: Deployment environment (default: staging)"
            echo "  --type: Deployment type - code or docker (default: code)"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            ;;
    esac
done

# Adjust names based on environment
if [[ "$ENVIRONMENT" == "production" ]]; then
    APP_NAME="comicguess-backend-prod"
    SKU="S1"  # Standard tier for production
else
    APP_NAME="comicguess-backend-staging"
fi

log "Starting deployment to $ENVIRONMENT environment..."
log "App Name: $APP_NAME"
log "Resource Group: $RESOURCE_GROUP"
log "Deployment Type: $DEPLOY_TYPE"

# Create resource group if it doesn't exist
log "Ensuring resource group exists..."
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

# Create App Service Plan if it doesn't exist
log "Ensuring App Service Plan exists..."
PLAN_NAME="${APP_NAME}-plan"
if ! az appservice plan show --name "$PLAN_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    log "Creating App Service Plan..."
    az appservice plan create \
        --name "$PLAN_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku "$SKU" \
        --is-linux \
        --output none
else
    log "App Service Plan already exists"
fi

# Create Web App if it doesn't exist
log "Ensuring Web App exists..."
if ! az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
    log "Creating Web App..."
    az webapp create \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --plan "$PLAN_NAME" \
        --runtime "$RUNTIME" \
        --output none
else
    log "Web App already exists"
fi

# Configure application settings
log "Configuring application settings..."
az webapp config appsettings set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        WEBSITES_PORT=8000 \
        PYTHONPATH=/home/site/wwwroot \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true \
        ENABLE_ORYX_BUILD=true \
        WEBSITES_ENABLE_APP_SERVICE_STORAGE=false \
        WEBSITE_HTTPLOGGING_RETENTION_DAYS=7 \
        WEBSITE_TIME_ZONE=UTC \
        WEBSITE_RUN_FROM_PACKAGE=1 \
    --output none

# Set startup command
log "Setting startup command..."
az webapp config set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --startup-file "uvicorn main:app --host 0.0.0.0 --port 8000" \
    --output none

# Configure health check
log "Configuring health check..."
az webapp config set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --generic-configurations '{"healthCheckPath": "/health"}' \
    --output none

# Deploy based on type
if [[ "$DEPLOY_TYPE" == "docker" ]]; then
    log "Deploying using Docker container..."
    
    # Build and push Docker image
    REGISTRY_NAME="comicguessregistry"
    IMAGE_NAME="$REGISTRY_NAME.azurecr.io/comicguess-backend:$ENVIRONMENT"
    
    # Build image
    log "Building Docker image..."
    docker build -t "$IMAGE_NAME" .
    
    # Push to registry (assumes registry exists and user is logged in)
    log "Pushing Docker image to registry..."
    docker push "$IMAGE_NAME"
    
    # Configure web app to use container
    az webapp config container set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --docker-custom-image-name "$IMAGE_NAME" \
        --output none
        
else
    log "Deploying using source code..."
    
    # Deploy from local source
    az webapp up \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --runtime "$RUNTIME" \
        --sku "$SKU" \
        --output none
fi

# Configure CORS
log "Configuring CORS..."
FRONTEND_URL="https://comicguess.vercel.app"
if [[ "$ENVIRONMENT" == "staging" ]]; then
    FRONTEND_URL="https://comicguess-staging.vercel.app"
fi

az webapp cors add \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --allowed-origins "$FRONTEND_URL" "https://localhost:3000" "http://localhost:3000" \
    --output none

# Enable logging
log "Enabling application logging..."
az webapp log config \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --application-logging filesystem \
    --level information \
    --output none

# Get the app URL
APP_URL=$(az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" --query "defaultHostName" --output tsv)

log "Deployment completed successfully!"
log "App URL: https://$APP_URL"
log "Health Check: https://$APP_URL/health"

# Test the deployment
log "Testing deployment..."
sleep 30  # Wait for app to start

if curl -f "https://$APP_URL/health" > /dev/null 2>&1; then
    log "✅ Health check passed!"
else
    warn "❌ Health check failed. Check the application logs."
    log "View logs with: az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
fi

log "Deployment script completed."