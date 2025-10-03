// Storage Account module
@description('Storage account name')
param accountName string

@description('Location for the storage account')
param location string

@description('Environment name')
param environment string

@description('Storage tier')
@allowed(['Standard_LRS', 'Standard_GRS', 'Standard_RAGRS', 'Premium_LRS'])
param tier string = 'Standard_LRS'

@description('Tags to apply to resources')
param tags object = {}

// Container names
var containerNames = [
  'character-images'
  'backups'
  'logs'
]

// Storage Account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: accountName
  location: location
  tags: tags
  sku: {
    name: tier
  }
  kind: 'StorageV2'
  properties: {
    dnsEndpointType: 'Standard'
    defaultToOAuthAuthentication: false
    publicNetworkAccess: 'Enabled'
    allowCrossTenantReplication: false
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: true
    allowSharedKeyAccess: true
    networkAcls: {
      bypass: 'AzureServices'
      virtualNetworkRules: []
      ipRules: []
      defaultAction: 'Allow'
    }
    supportsHttpsTrafficOnly: true
    encryption: {
      requireInfrastructureEncryption: environment == 'production'
      services: {
        file: {
          keyType: 'Account'
          enabled: true
        }
        blob: {
          keyType: 'Account'
          enabled: true
        }
      }
      keySource: 'Microsoft.Storage'
    }
    accessTier: 'Hot'
  }
}

// Blob Service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    changeFeed: {
      enabled: false
    }
    restorePolicy: {
      enabled: false
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: environment == 'production' ? 30 : 7
    }
    deleteRetentionPolicy: {
      enabled: true
      days: environment == 'production' ? 30 : 7
    }
    isVersioningEnabled: environment == 'production'
  }
}

// Containers
resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = [for containerName in containerNames: {
  parent: blobService
  name: containerName
  properties: {
    immutableStorageWithVersioning: {
      enabled: false
    }
    defaultEncryptionScope: '$account-encryption-key'
    denyEncryptionScopeOverride: false
    publicAccess: containerName == 'character-images' ? 'Blob' : 'None'
  }
}]

// Lifecycle Management Policy
resource lifecyclePolicy 'Microsoft.Storage/storageAccounts/managementPolicies@2023-01-01' = {
  parent: storageAccount
  name: 'default'
  properties: {
    policy: {
      rules: [
        {
          enabled: true
          name: 'DeleteOldLogs'
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                'logs/'
              ]
            }
            actions: {
              baseBlob: {
                delete: {
                  daysAfterModificationGreaterThan: environment == 'production' ? 90 : 30
                }
              }
            }
          }
        }
        {
          enabled: true
          name: 'ArchiveOldBackups'
          type: 'Lifecycle'
          definition: {
            filters: {
              blobTypes: [
                'blockBlob'
              ]
              prefixMatch: [
                'backups/'
              ]
            }
            actions: {
              baseBlob: {
                tierToArchive: {
                  daysAfterModificationGreaterThan: environment == 'production' ? 30 : 7
                }
                delete: {
                  daysAfterModificationGreaterThan: environment == 'production' ? 365 : 90
                }
              }
            }
          }
        }
      ]
    }
  }
}

// Outputs
output id string = storageAccount.id
output name string = storageAccount.name
output primaryKey string = storageAccount.listKeys().keys[0].value
output primaryEndpoint string = storageAccount.properties.primaryEndpoints.blob
output containerNames array = containerNames