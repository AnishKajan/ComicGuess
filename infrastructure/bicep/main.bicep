// Main Bicep template for ComicGuess infrastructure
@description('Environment name (dev, staging, production)')
@allowed(['dev', 'staging', 'production'])
param environment string

@description('Location for all resources')
param location string = resourceGroup().location

@description('Application name prefix')
param appName string = 'comicguess'

@description('Tags to apply to all resources')
param tags object = {
  application: 'ComicGuess'
  environment: environment
  managedBy: 'bicep'
}

// Environment-specific configuration
var environmentConfig = {
  dev: {
    cosmosDbThroughput: 400
    appServiceSku: 'B1'
    appServiceInstances: 1
    storageTier: 'Standard_LRS'
    functionAppSku: 'Y1'
    enableBackup: false
    enableGeoReplication: false
  }
  staging: {
    cosmosDbThroughput: 800
    appServiceSku: 'S1'
    appServiceInstances: 2
    storageTier: 'Standard_GRS'
    functionAppSku: 'EP1'
    enableBackup: true
    enableGeoReplication: false
  }
  production: {
    cosmosDbThroughput: 2000
    appServiceSku: 'P1V2'
    appServiceInstances: 3
    storageTier: 'Standard_RAGRS'
    functionAppSku: 'EP2'
    enableBackup: true
    enableGeoReplication: true
  }
}

var config = environmentConfig[environment]

// Generate unique names
var cosmosDbAccountName = '${appName}-${environment}-cosmos-${uniqueString(resourceGroup().id)}'
var storageAccountName = '${appName}${environment}storage${uniqueString(resourceGroup().id)}'
var appServicePlanName = '${appName}-${environment}-plan'
var appServiceName = '${appName}-backend-${environment}'
var functionAppName = '${appName}-${environment}-functions'
var applicationInsightsName = '${appName}-${environment}-insights'
var keyVaultName = '${appName}-${environment}-kv-${uniqueString(resourceGroup().id)}'

// Deploy Cosmos DB
module cosmosDb 'modules/cosmosdb.bicep' = {
  name: 'cosmosdb-deployment'
  params: {
    accountName: cosmosDbAccountName
    location: location
    environment: environment
    throughput: config.cosmosDbThroughput
    enableBackup: config.enableBackup
    enableGeoReplication: config.enableGeoReplication
    tags: tags
  }
}

// Deploy Storage Account
module storage 'modules/storage.bicep' = {
  name: 'storage-deployment'
  params: {
    accountName: storageAccountName
    location: location
    environment: environment
    tier: config.storageTier
    tags: tags
  }
}

// Deploy Application Insights
module applicationInsights 'modules/application-insights.bicep' = {
  name: 'app-insights-deployment'
  params: {
    name: applicationInsightsName
    location: location
    environment: environment
    tags: tags
  }
}

// Deploy Key Vault
module keyVault 'modules/key-vault.bicep' = {
  name: 'key-vault-deployment'
  params: {
    name: keyVaultName
    location: location
    environment: environment
    tags: tags
  }
}

// Deploy App Service Plan
module appServicePlan 'modules/app-service-plan.bicep' = {
  name: 'app-service-plan-deployment'
  params: {
    name: appServicePlanName
    location: location
    environment: environment
    sku: config.appServiceSku
    capacity: config.appServiceInstances
    tags: tags
  }
}

// Deploy App Service
module appService 'modules/app-service.bicep' = {
  name: 'app-service-deployment'
  params: {
    name: appServiceName
    location: location
    environment: environment
    appServicePlanId: appServicePlan.outputs.id
    applicationInsightsInstrumentationKey: applicationInsights.outputs.instrumentationKey
    cosmosDbEndpoint: cosmosDb.outputs.endpoint
    cosmosDbPrimaryKey: cosmosDb.outputs.primaryKey
    cosmosDbDatabaseName: cosmosDb.outputs.databaseName
    storageAccountName: storage.outputs.name
    storageAccountKey: storage.outputs.primaryKey
    keyVaultName: keyVault.outputs.name
    tags: tags
  }
}

// Deploy Function App
module functionApp 'modules/function-app.bicep' = {
  name: 'function-app-deployment'
  params: {
    name: functionAppName
    location: location
    environment: environment
    sku: config.functionAppSku
    storageAccountName: storage.outputs.name
    storageAccountKey: storage.outputs.primaryKey
    applicationInsightsInstrumentationKey: applicationInsights.outputs.instrumentationKey
    cosmosDbEndpoint: cosmosDb.outputs.endpoint
    cosmosDbPrimaryKey: cosmosDb.outputs.primaryKey
    cosmosDbDatabaseName: cosmosDb.outputs.databaseName
    tags: tags
  }
}

// Outputs
output cosmosDbEndpoint string = cosmosDb.outputs.endpoint
output cosmosDbDatabaseName string = cosmosDb.outputs.databaseName
output storageAccountName string = storage.outputs.name
output appServiceName string = appService.outputs.name
output appServiceUrl string = appService.outputs.url
output functionAppName string = functionApp.outputs.name
output applicationInsightsInstrumentationKey string = applicationInsights.outputs.instrumentationKey
output keyVaultName string = keyVault.outputs.name