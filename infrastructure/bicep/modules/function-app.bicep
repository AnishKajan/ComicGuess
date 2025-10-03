// Function App module
@description('Function App name')
param name string

@description('Location for the Function App')
param location string

@description('Environment name')
param environment string

@description('SKU for the Function App')
@allowed(['Y1', 'EP1', 'EP2', 'EP3'])
param sku string = 'Y1'

@description('Storage account name')
param storageAccountName string

@description('Storage account key')
@secure()
param storageAccountKey string

@description('Application Insights instrumentation key')
@secure()
param applicationInsightsInstrumentationKey string

@description('Cosmos DB endpoint')
param cosmosDbEndpoint string

@description('Cosmos DB primary key')
@secure()
param cosmosDbPrimaryKey string

@description('Cosmos DB database name')
param cosmosDbDatabaseName string

@description('Tags to apply to resources')
param tags object = {}

// Function App Service Plan (for Premium plans)
resource functionAppServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = if (sku != 'Y1') {
  name: '${name}-plan'
  location: location
  tags: tags
  sku: {
    name: sku
    tier: 'ElasticPremium'
  }
  kind: 'elastic'
  properties: {
    reserved: true
    maximumElasticWorkerCount: environment == 'production' ? 20 : 10
  }
}

// Function App
resource functionApp 'Microsoft.Web/sites@2023-01-01' = {
  name: name
  location: location
  tags: tags
  kind: 'functionapp,linux'
  properties: {
    serverFarmId: sku == 'Y1' ? null : functionAppServicePlan.id
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: sku != 'Y1'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      use32BitWorkerProcess: false
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccountKey};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccountName};AccountKey=${storageAccountKey};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: toLower(name)
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'PYTHON_ISOLATE_WORKER_DEPENDENCIES'
          value: '1'
        }
        {
          name: 'APP_ENV'
          value: environment
        }
        {
          name: 'COSMOS_ENDPOINT'
          value: cosmosDbEndpoint
        }
        {
          name: 'COSMOS_KEY'
          value: cosmosDbPrimaryKey
        }
        {
          name: 'COSMOS_DATABASE_NAME'
          value: cosmosDbDatabaseName
        }
        {
          name: 'AZURE_STORAGE_ACCOUNT_NAME'
          value: storageAccountName
        }
        {
          name: 'AZURE_STORAGE_ACCOUNT_KEY'
          value: storageAccountKey
        }
        {
          name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
          value: 'InstrumentationKey=${applicationInsightsInstrumentationKey}'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
      ]
    }
    httpsOnly: true
    clientAffinityEnabled: false
    publicNetworkAccess: 'Enabled'
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Outputs
output id string = functionApp.id
output name string = functionApp.name
output principalId string = functionApp.identity.principalId