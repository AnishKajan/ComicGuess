#!/bin/bash

# Infrastructure deployment script using Azure CLI and Bicep
set -e

# Default values
ENVIRONMENT=""
LOCATION="eastus"
RESOURCE_GROUP=""
SUBSCRIPTION_ID=""
DRY_RUN=false
VALIDATE_ONLY=false

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to show usage
show_usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Deploy ComicGuess infrastructure using Azure Bicep templates.

OPTIONS:
    -e, --environment ENVIRONMENT    Target environment (dev, staging, production)
    -l, --location LOCATION         Azure region (default: eastus)
    -g, --resource-group GROUP      Resource group name (auto-generated if not provided)
    -s, --subscription SUBSCRIPTION Subscription ID (uses current if not provided)
    -d, --dry-run                   Show what would be deployed without actually deploying
    -v, --validate-only             Only validate templates without deploying
    -h, --help                      Show this help message

EXAMPLES:
    $0 --environment dev
    $0 --environment production --location westus2
    $0 --environment staging --dry-run
    $0 --environment dev --validate-only

PREREQUISITES:
    - Azure CLI installed and logged in
    - Bicep CLI installed
    - Appropriate permissions in target subscription
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -l|--location)
            LOCATION="$2"
            shift 2
            ;;
        -g|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -s|--subscription)
            SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        -d|--dry-run)
            DRY_RUN=true
            shift
            ;;
        -v|--validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$ENVIRONMENT" ]]; then
    print_error "Environment is required. Use --environment to specify."
    show_usage
    exit 1
fi

if [[ ! "$ENVIRONMENT" =~ ^(dev|staging|production)$ ]]; then
    print_error "Environment must be one of: dev, staging, production"
    exit 1
fi

# Set default resource group if not provided
if [[ -z "$RESOURCE_GROUP" ]]; then
    RESOURCE_GROUP="comicguess-${ENVIRONMENT}-rg"
fi

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BICEP_DIR="$PROJECT_ROOT/infrastructure/bicep"

print_status "Starting infrastructure deployment..."
print_status "Environment: $ENVIRONMENT"
print_status "Location: $LOCATION"
print_status "Resource Group: $RESOURCE_GROUP"

# Check prerequisites
print_status "Checking prerequisites..."

# Check Azure CLI
if ! command -v az &> /dev/null; then
    print_error "Azure CLI is not installed. Please install it first."
    exit 1
fi

# Check Bicep CLI
if ! command -v bicep &> /dev/null; then
    print_error "Bicep CLI is not installed. Please install it first."
    exit 1
fi

# Check Azure login
if ! az account show &> /dev/null; then
    print_error "Not logged in to Azure. Please run 'az login' first."
    exit 1
fi

# Set subscription if provided
if [[ -n "$SUBSCRIPTION_ID" ]]; then
    print_status "Setting subscription to $SUBSCRIPTION_ID"
    az account set --subscription "$SUBSCRIPTION_ID"
fi

# Get current subscription info
CURRENT_SUBSCRIPTION=$(az account show --query "id" -o tsv)
SUBSCRIPTION_NAME=$(az account show --query "name" -o tsv)
print_status "Using subscription: $SUBSCRIPTION_NAME ($CURRENT_SUBSCRIPTION)"

# Validate Bicep templates
print_status "Validating Bicep templates..."
if ! bicep build "$BICEP_DIR/main.bicep" --stdout > /dev/null; then
    print_error "Bicep template validation failed"
    exit 1
fi
print_success "Bicep templates are valid"

# Create resource group if it doesn't exist
print_status "Ensuring resource group exists..."
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    if [[ "$DRY_RUN" == "true" ]]; then
        print_status "[DRY RUN] Would create resource group: $RESOURCE_GROUP"
    else
        print_status "Creating resource group: $RESOURCE_GROUP"
        az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
        print_success "Resource group created"
    fi
else
    print_status "Resource group already exists"
fi

# Prepare deployment parameters
DEPLOYMENT_NAME="comicguess-${ENVIRONMENT}-$(date +%Y%m%d-%H%M%S)"
PARAMETER_FILE="$BICEP_DIR/parameters/${ENVIRONMENT}.bicepparam"

if [[ ! -f "$PARAMETER_FILE" ]]; then
    print_error "Parameter file not found: $PARAMETER_FILE"
    exit 1
fi

# Validate deployment
print_status "Validating deployment..."
VALIDATION_RESULT=$(az deployment group validate \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$BICEP_DIR/main.bicep" \
    --parameters "@$PARAMETER_FILE" \
    --query "error" -o tsv 2>/dev/null || echo "validation-failed")

if [[ "$VALIDATION_RESULT" != "null" && "$VALIDATION_RESULT" != "" ]]; then
    print_error "Deployment validation failed:"
    az deployment group validate \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$BICEP_DIR/main.bicep" \
        --parameters "@$PARAMETER_FILE"
    exit 1
fi
print_success "Deployment validation passed"

# Exit if validate-only mode
if [[ "$VALIDATE_ONLY" == "true" ]]; then
    print_success "Validation completed successfully. Exiting (validate-only mode)."
    exit 0
fi

# Show what-if analysis
print_status "Generating deployment preview..."
if [[ "$DRY_RUN" == "true" ]]; then
    print_status "[DRY RUN] Deployment preview:"
    az deployment group what-if \
        --resource-group "$RESOURCE_GROUP" \
        --template-file "$BICEP_DIR/main.bicep" \
        --parameters "@$PARAMETER_FILE" \
        --result-format FullResourcePayloads
    
    print_status "[DRY RUN] Deployment would be executed with name: $DEPLOYMENT_NAME"
    print_success "Dry run completed. No resources were deployed."
    exit 0
fi

# Confirm deployment for production
if [[ "$ENVIRONMENT" == "production" ]]; then
    print_warning "You are about to deploy to PRODUCTION environment!"
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_status "Deployment cancelled by user"
        exit 0
    fi
fi

# Execute deployment
print_status "Starting deployment: $DEPLOYMENT_NAME"
print_status "This may take several minutes..."

DEPLOYMENT_START_TIME=$(date +%s)

az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "$BICEP_DIR/main.bicep" \
    --parameters "@$PARAMETER_FILE" \
    --name "$DEPLOYMENT_NAME" \
    --verbose

DEPLOYMENT_END_TIME=$(date +%s)
DEPLOYMENT_DURATION=$((DEPLOYMENT_END_TIME - DEPLOYMENT_START_TIME))

if [[ $? -eq 0 ]]; then
    print_success "Deployment completed successfully!"
    print_success "Duration: ${DEPLOYMENT_DURATION} seconds"
    
    # Get deployment outputs
    print_status "Retrieving deployment outputs..."
    OUTPUTS=$(az deployment group show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$DEPLOYMENT_NAME" \
        --query "properties.outputs" -o json)
    
    if [[ "$OUTPUTS" != "null" && "$OUTPUTS" != "{}" ]]; then
        print_status "Deployment outputs:"
        echo "$OUTPUTS" | jq -r 'to_entries[] | "\(.key): \(.value.value)"'
        
        # Save outputs to file
        OUTPUT_FILE="$PROJECT_ROOT/infrastructure/outputs/${ENVIRONMENT}-outputs.json"
        mkdir -p "$(dirname "$OUTPUT_FILE")"
        echo "$OUTPUTS" > "$OUTPUT_FILE"
        print_status "Outputs saved to: $OUTPUT_FILE"
    fi
    
    # Display next steps
    print_status "Next steps:"
    echo "1. Configure application secrets in Key Vault"
    echo "2. Deploy application code to App Service"
    echo "3. Deploy Function App code"
    echo "4. Configure custom domains and SSL certificates"
    echo "5. Set up monitoring and alerts"
    
else
    print_error "Deployment failed!"
    print_status "Check the deployment logs for details:"
    print_status "az deployment group show --resource-group $RESOURCE_GROUP --name $DEPLOYMENT_NAME"
    exit 1
fi