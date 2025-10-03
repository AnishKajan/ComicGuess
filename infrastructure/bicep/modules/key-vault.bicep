// Key Vault module
@description('Key Vault name')
param name string

@description('Location for Key Vault')
param location string

@description('Environment name')
param environment string

@description('Tags to apply to resources')
param tags object = {}

// Get current user/service principal for access policy
var currentUser = {
  objectId: '00000000-0000-0000-0000-000000000000' // This should be replaced with actual deployment principal
  tenantId: tenant().tenantId
}

// Key Vault
resource keyVault 'Microsoft.KeyVault/vaults@2023-02-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      family: 'A'
      name: 'standard'
    }
    tenantId: tenant().tenantId
    enabledForDeployment: false
    enabledForDiskEncryption: false
    enabledForTemplateDeployment: true
    enableSoftDelete: true
    softDeleteRetentionInDays: environment == 'production' ? 90 : 7
    enableRbacAuthorization: true
    publicNetworkAccess: 'Enabled'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: 'Allow'
      ipRules: []
      virtualNetworkRules: []
    }
  }
}

// Diagnostic settings for Key Vault
resource diagnosticSettings 'Microsoft.Insights/diagnosticSettings@2021-05-01-preview' = {
  name: '${name}-diagnostics'
  scope: keyVault
  properties: {
    logs: [
      {
        categoryGroup: 'allLogs'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: environment == 'production' ? 365 : 90
        }
      }
    ]
    metrics: [
      {
        category: 'AllMetrics'
        enabled: true
        retentionPolicy: {
          enabled: true
          days: environment == 'production' ? 365 : 90
        }
      }
    ]
  }
}

// Outputs
output id string = keyVault.id
output name string = keyVault.name
output uri string = keyVault.properties.vaultUri