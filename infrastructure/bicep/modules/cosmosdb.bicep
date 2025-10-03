// Cosmos DB module
@description('Cosmos DB account name')
param accountName string

@description('Location for the Cosmos DB account')
param location string

@description('Environment name')
param environment string

@description('Database throughput')
param throughput int = 400

@description('Enable backup')
param enableBackup bool = false

@description('Enable geo-replication')
param enableGeoReplication bool = false

@description('Tags to apply to resources')
param tags object = {}

// Database and container names
var databaseName = 'comicguess_${environment}'
var containerNames = [
  'users'
  'puzzles'
  'guesses'
]

// Consistency level based on environment
var consistencyLevel = environment == 'production' ? 'Strong' : 'Session'

// Backup policy
var backupPolicy = enableBackup ? {
  type: 'Periodic'
  periodicModeProperties: {
    backupIntervalInMinutes: 240
    backupRetentionIntervalInHours: environment == 'production' ? 2160 : 720 // 90 days for prod, 30 for others
    backupStorageRedundancy: 'Geo'
  }
} : {
  type: 'Periodic'
  periodicModeProperties: {
    backupIntervalInMinutes: 1440
    backupRetentionIntervalInHours: 168 // 7 days
    backupStorageRedundancy: 'Local'
  }
}

// Locations for geo-replication
var locations = enableGeoReplication ? [
  {
    locationName: location
    failoverPriority: 0
    isZoneRedundant: false
  }
  {
    locationName: location == 'eastus' ? 'westus' : 'eastus'
    failoverPriority: 1
    isZoneRedundant: false
  }
] : [
  {
    locationName: location
    failoverPriority: 0
    isZoneRedundant: false
  }
]

// Cosmos DB Account
resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'GlobalDocumentDB'
  properties: {
    consistencyPolicy: {
      defaultConsistencyLevel: consistencyLevel
    }
    locations: locations
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: enableGeoReplication
    enableMultipleWriteLocations: false
    backupPolicy: backupPolicy
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
    publicNetworkAccess: 'Enabled'
    networkAclBypass: 'AzureServices'
    disableKeyBasedMetadataWriteAccess: false
  }
}

// Database
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosDbAccount
  name: databaseName
  properties: {
    resource: {
      id: databaseName
    }
    options: environment == 'production' ? {
      throughput: throughput
    } : {}
  }
}

// Containers
resource containers 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = [for containerName in containerNames: {
  parent: database
  name: containerName
  properties: {
    resource: {
      id: containerName
      partitionKey: {
        paths: [
          containerName == 'users' ? '/id' : containerName == 'puzzles' ? '/id' : '/userId'
        ]
        kind: 'Hash'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
      defaultTtl: containerName == 'guesses' ? 7776000 : -1 // 90 days for guesses, never expire for others
    }
    options: environment != 'production' ? {} : {
      throughput: throughput / length(containerNames)
    }
  }
}]

// Outputs
output id string = cosmosDbAccount.id
output name string = cosmosDbAccount.name
output endpoint string = cosmosDbAccount.properties.documentEndpoint
output primaryKey string = cosmosDbAccount.listKeys().primaryMasterKey
output databaseName string = database.name
output containerNames array = containerNames