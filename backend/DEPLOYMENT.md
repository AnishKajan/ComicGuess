# Backend Deployment Guide

This document outlines the deployment process for the ComicGuess backend API.

## Prerequisites

1. **Cloud Account**: Active cloud service subscription
2. **Deployment Tools**: Installed and configured locally
3. **Docker**: For containerized deployments (optional)
4. **GitHub Repository**: Code must be in a GitHub repository

## Environment Setup

### Required Cloud Resources

Before deployment, ensure these cloud resources exist:

1. **Resource Group**: `comicguess-rg`
2. **Firebase Firestore**: Database service
3. **Firebase Storage**: For character images
4. **Hosting Service**: For backend deployment
5. **Secrets Management**: For secure configuration (recommended)

### Environment Variables

#### Required Variables

Configure these in your hosting service application settings:

```bash
# Application Configuration
APP_ENV=production
DEBUG=false
LOG_LEVEL=INFO

# Database Configuration
FIREBASE_PROJECT_ID=your-firebase-project-id
COSMOS_KEY=your-cosmos-primary-key
COSMOS_DATABASE_NAME=comicguess
COSMOS_CONTAINER_USERS=users
COSMOS_CONTAINER_PUZZLES=puzzles
COSMOS_CONTAINER_GUESSES=guesses

# Storage Configuration
AZURE_STORAGE_ACCOUNT_NAME=your-storage-account
AZURE_STORAGE_ACCOUNT_KEY=your-storage-key
AZURE_STORAGE_CONTAINER_NAME=character-images

# Authentication
JWT_SECRET_KEY=your-super-secret-jwt-key-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
SESSION_SECRET=your-session-secret-key

# CORS Configuration
ALLOWED_ORIGINS=https://comicguess.vercel.app,https://www.comicguess.com

# Rate Limiting
RATE_LIMIT_REQUESTS=10
RATE_LIMIT_WINDOW=60

# Azure App Service Specific
WEBSITES_PORT=8000
PYTHONPATH=/home/site/wwwroot
SCM_DO_BUILD_DURING_DEPLOYMENT=true
ENABLE_ORYX_BUILD=true
```

#### GitHub Secrets

Configure these secrets in your GitHub repository:

```bash
# Azure Configuration
AZURE_CREDENTIALS={"clientId":"...","clientSecret":"...","subscriptionId":"...","tenantId":"..."}
AZURE_RESOURCE_GROUP=comicguess-rg

# Environment-specific secrets
STAGING_COSMOS_ENDPOINT=https://staging-cosmos.documents.azure.com:443/
STAGING_COSMOS_KEY=staging-cosmos-key
PROD_COSMOS_ENDPOINT=https://prod-cosmos.documents.azure.com:443/
PROD_COSMOS_KEY=prod-cosmos-key

# Container Registry (if using Docker)
REGISTRY_LOGIN_SERVER=comicguessregistry.azurecr.io
REGISTRY_USERNAME=comicguessregistry
REGISTRY_PASSWORD=registry-password
```

## Deployment Methods

### 1. Automated Deployment (Recommended)

The application automatically deploys when code is pushed:

- **Production**: Push to `main` branch
- **Staging**: Push to `develop` branch
- **Preview**: Create a pull request

### 2. Manual Deployment using Azure CLI

#### Quick Deployment

```bash
# Navigate to backend directory
cd backend

# Deploy using the deployment script
./deploy/app-service-deploy.sh --env production --type code
```

#### Step-by-step Manual Deployment

```bash
# Login to Azure
az login

# Set default subscription
az account set --subscription "your-subscription-id"

# Create resource group (if not exists)
az group create --name comicguess-rg --location eastus

# Create App Service Plan
az appservice plan create \
  --name comicguess-backend-plan \
  --resource-group comicguess-rg \
  --location eastus \
  --sku B1 \
  --is-linux

# Create Web App
az webapp create \
  --name comicguess-backend-prod \
  --resource-group comicguess-rg \
  --plan comicguess-backend-plan \
  --runtime "PYTHON:3.11"

# Configure startup command
az webapp config set \
  --name comicguess-backend-prod \
  --resource-group comicguess-rg \
  --startup-file "uvicorn main:app --host 0.0.0.0 --port 8000"

# Deploy code
az webapp up \
  --name comicguess-backend-prod \
  --resource-group comicguess-rg \
  --runtime "PYTHON:3.11"
```

### 3. Docker Deployment

#### Build and Deploy Container

```bash
# Build Docker image
docker build -t comicguess-backend .

# Tag for Azure Container Registry
docker tag comicguess-backend comicguessregistry.azurecr.io/comicguess-backend:latest

# Push to registry
docker push comicguessregistry.azurecr.io/comicguess-backend:latest

# Deploy to App Service
az webapp config container set \
  --name comicguess-backend-prod \
  --resource-group comicguess-rg \
  --docker-custom-image-name comicguessregistry.azurecr.io/comicguess-backend:latest
```

## Configuration Management

### Environment-Specific Settings

The application uses different configuration classes for each environment:

- **Development**: `DevelopmentSettings`
- **Staging**: `StagingSettings`
- **Production**: `ProductionSettings`
- **Test**: `TestSettings`

### Azure Key Vault Integration (Recommended)

For production deployments, use Azure Key Vault for sensitive data:

```bash
# Create Key Vault
az keyvault create \
  --name comicguess-keyvault \
  --resource-group comicguess-rg \
  --location eastus

# Add secrets
az keyvault secret set --vault-name comicguess-keyvault --name "cosmos-key" --value "your-cosmos-key"
az keyvault secret set --vault-name comicguess-keyvault --name "jwt-secret" --value "your-jwt-secret"

# Grant App Service access to Key Vault
az webapp identity assign --name comicguess-backend-prod --resource-group comicguess-rg
az keyvault set-policy \
  --name comicguess-keyvault \
  --object-id $(az webapp identity show --name comicguess-backend-prod --resource-group comicguess-rg --query principalId -o tsv) \
  --secret-permissions get list
```

## Health Checks and Monitoring

### Health Check Endpoints

The application provides several health check endpoints:

- `/health`: Basic application health
- `/user/health`: User service health
- Custom health checks for database and storage connectivity

### Application Insights Integration

Enable Application Insights for monitoring:

```bash
# Create Application Insights
az monitor app-insights component create \
  --app comicguess-backend \
  --location eastus \
  --resource-group comicguess-rg

# Configure App Service to use Application Insights
az webapp config appsettings set \
  --name comicguess-backend-prod \
  --resource-group comicguess-rg \
  --settings APPINSIGHTS_INSTRUMENTATIONKEY="your-instrumentation-key"
```

### Log Streaming

View real-time logs:

```bash
# Stream logs
az webapp log tail --name comicguess-backend-prod --resource-group comicguess-rg

# Download logs
az webapp log download --name comicguess-backend-prod --resource-group comicguess-rg
```

## Security Configuration

### HTTPS and SSL

HTTPS is automatically enabled for Azure App Service. For custom domains:

```bash
# Add custom domain
az webapp config hostname add \
  --webapp-name comicguess-backend-prod \
  --resource-group comicguess-rg \
  --hostname api.comicguess.com

# Enable SSL
az webapp config ssl bind \
  --certificate-thumbprint your-cert-thumbprint \
  --ssl-type SNI \
  --name comicguess-backend-prod \
  --resource-group comicguess-rg
```

### Network Security

Configure network access restrictions:

```bash
# Restrict access to specific IPs (optional)
az webapp config access-restriction add \
  --name comicguess-backend-prod \
  --resource-group comicguess-rg \
  --rule-name "AllowFrontend" \
  --action Allow \
  --ip-address "frontend-ip-range" \
  --priority 100
```

## Performance Optimization

### Scaling Configuration

Configure auto-scaling:

```bash
# Enable auto-scaling
az monitor autoscale create \
  --resource-group comicguess-rg \
  --resource comicguess-backend-prod \
  --resource-type Microsoft.Web/sites \
  --name comicguess-backend-autoscale \
  --min-count 1 \
  --max-count 3 \
  --count 1

# Add CPU-based scaling rule
az monitor autoscale rule create \
  --resource-group comicguess-rg \
  --autoscale-name comicguess-backend-autoscale \
  --condition "Percentage CPU > 70 avg 5m" \
  --scale out 1
```

### Application Performance

- **Connection Pooling**: Configured in database connection settings
- **Async Processing**: FastAPI with async/await patterns
- **Caching**: Redis integration for frequently accessed data
- **CDN Integration**: Azure CDN for static assets

## Troubleshooting

### Common Issues

1. **Startup Failures**
   ```bash
   # Check startup logs
   az webapp log tail --name comicguess-backend-prod --resource-group comicguess-rg
   
   # Verify startup command
   az webapp config show --name comicguess-backend-prod --resource-group comicguess-rg
   ```

2. **Database Connection Issues**
   ```bash
   # Test Cosmos DB connectivity
   az cosmosdb check-name-exists --name your-cosmos-account
   
   # Verify connection string
   az webapp config appsettings list --name comicguess-backend-prod --resource-group comicguess-rg
   ```

3. **Storage Access Issues**
   ```bash
   # Test storage account access
   az storage account check-name --name your-storage-account
   
   # Verify storage keys
   az storage account keys list --account-name your-storage-account --resource-group comicguess-rg
   ```

### Debug Commands

```bash
# SSH into App Service container
az webapp ssh --name comicguess-backend-prod --resource-group comicguess-rg

# Run health check locally
curl https://comicguess-backend-prod.azurewebsites.net/health

# Test API endpoints
curl -X POST https://comicguess-backend-prod.azurewebsites.net/guess \
  -H "Content-Type: application/json" \
  -d '{"userId":"test","universe":"marvel","guess":"Spider-Man"}'
```

## Rollback Procedures

### Using Azure Portal

1. Navigate to App Service in Azure Portal
2. Go to "Deployment Center"
3. Select previous successful deployment
4. Click "Redeploy"

### Using Azure CLI

```bash
# List deployment history
az webapp deployment list --name comicguess-backend-prod --resource-group comicguess-rg

# Redeploy specific version
az webapp deployment source config-zip \
  --name comicguess-backend-prod \
  --resource-group comicguess-rg \
  --src previous-version.zip
```

### Using GitHub Actions

1. Navigate to GitHub Actions tab
2. Find previous successful workflow run
3. Click "Re-run jobs"

## Disaster Recovery

### Backup Strategy

1. **Database Backups**: Cosmos DB automatic backups (enabled by default)
2. **Storage Backups**: Azure Blob Storage geo-redundancy
3. **Application Code**: Version control in GitHub
4. **Configuration**: Infrastructure as Code templates

### Recovery Procedures

1. **Database Recovery**:
   ```bash
   # Restore from backup (contact Azure support for point-in-time restore)
   az cosmosdb restore --help
   ```

2. **Storage Recovery**:
   ```bash
   # Enable soft delete for blob storage
   az storage account blob-service-properties update \
     --account-name your-storage-account \
     --enable-delete-retention true \
     --delete-retention-days 7
   ```

3. **Application Recovery**:
   - Redeploy from GitHub
   - Restore from Docker image
   - Deploy to secondary region

## Cost Optimization

### Resource Right-Sizing

- **Development**: B1 (Basic) tier
- **Staging**: B2 (Basic) tier  
- **Production**: S1 (Standard) tier with auto-scaling

### Cost Monitoring

```bash
# Set up budget alerts
az consumption budget create \
  --budget-name comicguess-backend-budget \
  --amount 100 \
  --time-grain Monthly \
  --start-date 2024-01-01 \
  --end-date 2024-12-31
```

## Support and Maintenance

### Regular Maintenance Tasks

1. **Security Updates**: Monthly dependency updates
2. **Performance Monitoring**: Weekly performance reviews
3. **Cost Review**: Monthly cost analysis
4. **Backup Verification**: Quarterly backup tests

### Support Contacts

- **Azure Support**: Azure Portal support tickets
- **Application Issues**: GitHub Issues
- **Security Issues**: Security team contact