# ComicGuess Infrastructure

This directory contains infrastructure setup and deployment scripts for Azure services.

## Azure Services

### 1. Azure Static Web Apps (Frontend Hosting)

Host the Next.js frontend with automatic builds and deployments.

```bash
# Create Static Web App
az staticwebapp create \
  --name comicguess-frontend \
  --resource-group comicguess-rg \
  --source https://github.com/your-org/comicguess \
  --branch main \
  --app-location "/frontend" \
  --output-location "out" \
  --login-with-github

# Configure custom domain (optional)
az staticwebapp hostname set \
  --name comicguess-frontend \
  --hostname www.comicguess.com
```

### 2. Azure Functions (Serverless Backend)

Timer-triggered function that runs at midnight UTC to update daily puzzles.

```bash
# Create Function App
az functionapp create \
  --resource-group comicguess-rg \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.11 \
  --functions-version 4 \
  --name comicguess-functions \
  --storage-account comicguessstorage

# Deploy function code
func azure functionapp publish comicguess-functions
```

**Function Structure:**
- `DailyPuzzleUpdater/`: Timer trigger (0 0 * * *) - runs at midnight UTC
- `PuzzleGenerator/`: HTTP trigger for manual puzzle generation
- `ImageProcessor/`: Blob trigger for image optimization

### 3. Azure Blob Storage (Image Storage)

Store character images with CDN integration.

```bash
# Create storage account
az storage account create \
  --name comicguessstorage \
  --resource-group comicguess-rg \
  --location eastus \
  --sku Standard_LRS \
  --kind StorageV2

# Create containers
az storage container create \
  --name character-images \
  --account-name comicguessstorage \
  --public-access blob

az storage container create \
  --name processed-images \
  --account-name comicguessstorage \
  --public-access blob
```

**Container Structure:**
- `character-images/`: Original character images
- `processed-images/`: Optimized/resized images
- `thumbnails/`: Small preview images

### 4. Azure App Service (FastAPI Backend)

Host the FastAPI backend with auto-scaling.

```bash
# Create App Service Plan
az appservice plan create \
  --name comicguess-plan \
  --resource-group comicguess-rg \
  --sku B1 \
  --is-linux

# Create Web App
az webapp create \
  --resource-group comicguess-rg \
  --plan comicguess-plan \
  --name comicguess-api \
  --runtime "PYTHON|3.11"

# Configure deployment
az webapp deployment source config \
  --name comicguess-api \
  --resource-group comicguess-rg \
  --repo-url https://github.com/your-org/comicguess \
  --branch main \
  --manual-integration
```

### 5. Azure Cosmos DB (Database)

Already configured. Connection details:
- Account: `cg-cosmos-prod`
- Database: `comicguessdb`
- Containers: `users`, `streaks`, `puzzles`, `guesses`

## Environment Variables

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=https://comicguess-api.azurewebsites.net
NEXT_PUBLIC_CDN_URL=https://comicguessstorage.blob.core.windows.net
```

### Backend (.env)
```bash
# Cosmos DB
COSMOS_ACCOUNT_URI=https://cg-cosmos-prod.documents.azure.com:443/
COSMOS_ACCOUNT_KEY=<from-azure-portal>
COSMOS_DB_NAME=comicguessdb
COSMOS_CONTAINER_USERS=users
COSMOS_CONTAINER_STREAKS=streaks

# Blob Storage
BLOB_ACCOUNT_URL=https://comicguessstorage.blob.core.windows.net
BLOB_SAS_TOKEN=<from-azure-portal>

# App Settings
APP_ENV=production
ALLOWED_ORIGINS=https://www.comicguess.com,https://comicguess.com
```

### Azure Functions (local.settings.json)
```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "DefaultEndpointsProtocol=https;AccountName=comicguessstorage;AccountKey=<key>",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "COSMOS_ACCOUNT_URI": "https://cg-cosmos-prod.documents.azure.com:443/",
    "COSMOS_ACCOUNT_KEY": "<key>",
    "COSMOS_DB_NAME": "comicguessdb"
  }
}
```

## Deployment Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml
name: Deploy to Azure

on:
  push:
    branches: [main]

jobs:
  deploy-frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Static Web Apps
        uses: Azure/static-web-apps-deploy@v1
        with:
          azure_static_web_apps_api_token: ${{ secrets.AZURE_STATIC_WEB_APPS_API_TOKEN }}
          repo_token: ${{ secrets.GITHUB_TOKEN }}
          action: "upload"
          app_location: "/frontend"
          output_location: "out"

  deploy-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to App Service
        uses: azure/webapps-deploy@v2
        with:
          app-name: 'comicguess-api'
          publish-profile: ${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
          package: './backend'

  deploy-functions:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Deploy to Azure Functions
        uses: Azure/functions-action@v1
        with:
          app-name: 'comicguess-functions'
          package: './functions'
          publish-profile: ${{ secrets.AZURE_FUNCTIONS_PUBLISH_PROFILE }}
```

## Monitoring & Logging

### Application Insights
```bash
# Create Application Insights
az monitor app-insights component create \
  --app comicguess-insights \
  --location eastus \
  --resource-group comicguess-rg
```

### Log Analytics
```bash
# Create Log Analytics Workspace
az monitor log-analytics workspace create \
  --resource-group comicguess-rg \
  --workspace-name comicguess-logs
```

## Security

### Key Vault
```bash
# Create Key Vault
az keyvault create \
  --name comicguess-vault \
  --resource-group comicguess-rg \
  --location eastus

# Store secrets
az keyvault secret set \
  --vault-name comicguess-vault \
  --name "CosmosAccountKey" \
  --value "<cosmos-key>"
```

### Managed Identity
```bash
# Enable managed identity for App Service
az webapp identity assign \
  --name comicguess-api \
  --resource-group comicguess-rg

# Grant Key Vault access
az keyvault set-policy \
  --name comicguess-vault \
  --object-id <managed-identity-id> \
  --secret-permissions get list
```

## Cost Optimization

### Resource Tagging
```bash
# Tag resources for cost tracking
az resource tag \
  --tags Environment=Production Project=ComicGuess \
  --ids /subscriptions/<sub-id>/resourceGroups/comicguess-rg
```

### Auto-scaling
```bash
# Configure auto-scaling for App Service
az monitor autoscale create \
  --resource-group comicguess-rg \
  --resource comicguess-api \
  --resource-type Microsoft.Web/serverfarms \
  --name comicguess-autoscale \
  --min-count 1 \
  --max-count 3 \
  --count 1
```

## Backup & Disaster Recovery

### Cosmos DB Backup
- Automatic backups enabled (default)
- Point-in-time restore available
- Cross-region replication configured

### Blob Storage Backup
```bash
# Enable soft delete
az storage account blob-service-properties update \
  --account-name comicguessstorage \
  --enable-delete-retention true \
  --delete-retention-days 30
```

## Next Steps

1. **Set up Azure DevOps or GitHub Actions** for CI/CD
2. **Configure Application Insights** for monitoring
3. **Set up Azure CDN** for global content delivery
4. **Implement Azure Key Vault** for secret management
5. **Configure custom domains** and SSL certificates
6. **Set up backup and disaster recovery** procedures

## Local Development

All services should work locally without Azure dependencies:
- Use Cosmos DB Emulator for local development
- Use local file storage instead of Blob Storage
- Mock Azure Functions with local HTTP endpoints

## Support

For deployment issues, check:
1. Azure Portal logs
2. Application Insights telemetry
3. GitHub Actions workflow logs
4. App Service deployment logs