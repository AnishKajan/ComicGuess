// App Service Plan module
@description('App Service Plan name')
param name string

@description('Location for the App Service Plan')
param location string

@description('Environment name')
param environment string

@description('SKU for the App Service Plan')
@allowed(['B1', 'B2', 'B3', 'S1', 'S2', 'S3', 'P1V2', 'P2V2', 'P3V2'])
param sku string = 'B1'

@description('Number of instances')
param capacity int = 1

@description('Tags to apply to resources')
param tags object = {}

// App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2023-01-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
    capacity: capacity
  }
  kind: 'linux'
  properties: {
    reserved: true
    targetWorkerCount: capacity
    targetWorkerSizeId: 0
  }
}

// Outputs
output id string = appServicePlan.id
output name string = appServicePlan.name