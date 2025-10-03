// App Service module
@description('App Service name')
param name string

@description('Location for the App Service')
param location string

@description('Environment name')
param environment string

@description('App Service Plan resource ID')
param appServicePlanId string

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

@description('Storage account name')
param storageAccountName string

@description('Storage account key')
@secure()
param storageAccountKey string

@description('Key Vault name')
param keyVaultName string

@description('Tags to apply to resources')
param tags object = {}

// App Service
resource appService 'Microsoft.Web/sites@2023-01-01' = {
  name: name
  location: location
  tags: tags
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlanId
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: environment != 'dev'
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      httpLoggingEnabled: true
      logsDirectorySizeLimit: 35
      detailedErrorLoggingEnabled: true
      requestTracingEnabled: true
      remoteDebuggingEnabled: false
      webSocketsEnabled: false
      use32BitWorkerProcess: false
      managedPipelineMode: 'Integrated'
      appSettings: [
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
          name: 'KEY_VAULT_NAME'
          value: keyVaultName
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
          value: 'true'
        }
        {
          name: 'ENABLE_ORYX_BUILD'
          value: 'true'
        }
      ]
      connectionStrings: [
        {
          name: 'DefaultConnection'
          connectionString: 'AccountEndpoint=${cosmosDbEndpoint};AccountKey=${cosmosDbPrimaryKey};Database=${cosmosDbDatabaseName}'
          type: 'Custom'
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

// Deployment slots for staging and production
resource stagingSlot 'Microsoft.Web/sites/slots@2023-01-01' = if (environment != 'dev') {
  parent: appService
  name: 'staging'
  location: location
  tags: tags
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlanId
    siteConfig: {
      linuxFxVersion: 'PYTHON|3.11'
      alwaysOn: true
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      scmMinTlsVersion: '1.2'
      http20Enabled: true
      appSettings: [
        {
          name: 'APP_ENV'
          value: '${environment}-staging'
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
      ]
    }
    httpsOnly: true
    clientAffinityEnabled: false
  }
  identity: {
    type: 'SystemAssigned'
  }
}

// Auto-scaling rules for production
resource autoScaleSettings 'Microsoft.Insights/autoscalesettings@2022-10-01' = if (environment == 'production') {
  name: '${name}-autoscale'
  location: location
  tags: tags
  properties: {
    profiles: [
      {
        name: 'Default'
        capacity: {
          minimum: '2'
          maximum: '10'
          default: '3'
        }
        rules: [
          {
            metricTrigger: {
              metricName: 'CpuPercentage'
              metricResourceUri: appServicePlanId
              timeGrain: 'PT1M'
              statistic: 'Average'
              timeWindow: 'PT5M'
              timeAggregation: 'Average'
              operator: 'GreaterThan'
              threshold: 70
            }
            scaleAction: {
              direction: 'Increase'
              type: 'ChangeCount'
              value: '1'
              cooldown: 'PT5M'
            }
          }
          {
            metricTrigger: {
              metricName: 'CpuPercentage'
              metricResourceUri: appServicePlanId
              timeGrain: 'PT1M'
              statistic: 'Average'
              timeWindow: 'PT5M'
              timeAggregation: 'Average'
              operator: 'LessThan'
              threshold: 30
            }
            scaleAction: {
              direction: 'Decrease'
              type: 'ChangeCount'
              value: '1'
              cooldown: 'PT10M'
            }
          }
        ]
      }
    ]
    enabled: true
    targetResourceUri: appServicePlanId
  }
}

// Outputs
output id string = appService.id
output name string = appService.name
output url string = 'https://${appService.properties.defaultHostName}'
output principalId string = appService.identity.principalId
output stagingSlotName string = environment != 'dev' ? stagingSlot.name : ''