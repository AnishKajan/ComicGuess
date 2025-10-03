@description('Cosmos DB with autoscale configuration optimized for cost')
param cosmosAccountName string
param location string = resourceGroup().location
param environment string
param maxThroughput int = 4000
param minThroughput int = 400

// Cosmos DB Account with optimized settings
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: cosmosAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session' // Cost-effective consistency level
    }
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false // Disable for cost optimization in non-prod
      }
    ]
    databaseAccountOfferType: 'Standard'
    enableAutomaticFailover: environment == 'production'
    enableMultipleWriteLocations: false // Single region for cost optimization
    capabilities: [
      {
        name: 'EnableServerless' // Consider serverless for dev/staging
      }
    ]
    backupPolicy: {
      type: 'Periodic'
      periodicModeProperties: {
        backupIntervalInMinutes: environment == 'production' ? 240 : 1440 // Less frequent backups for non-prod
        backupRetentionIntervalInHours: environment == 'production' ? 720 : 168 // 30 days prod, 7 days non-prod
        backupStorageRedundancy: environment == 'production' ? 'Geo' : 'Local'
      }
    }
  }
  tags: {
    Environment: environment
    CostCenter: 'ComicGuess'
    AutoShutdown: environment != 'production' ? 'true' : 'false'
  }
}

// Database with autoscale throughput
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2023-04-15' = {
  parent: cosmosAccount
  name: 'comicguess'
  properties: {
    resource: {
      id: 'comicguess'
    }
    options: environment == 'production' ? {
      autoscaleSettings: {
        maxThroughput: maxThroughput
      }
    } : {
      throughput: minThroughput // Fixed throughput for non-prod
    }
  }
}

// Containers with optimized partition strategies
var containers = [
  {
    name: 'users'
    partitionKey: '/id'
    defaultTtl: -1
    indexingPolicy: {
      indexingMode: 'consistent'
      includedPaths: [
        {
          path: '/id/?'
        }
        {
          path: '/username/?'
        }
      ]
      excludedPaths: [
        {
          path: '/*' // Exclude all other paths to reduce RU consumption
        }
      ]
    }
  }
  {
    name: 'puzzles'
    partitionKey: '/id'
    defaultTtl: 31536000 // 1 year TTL for automatic cleanup
    indexingPolicy: {
      indexingMode: 'consistent'
      includedPaths: [
        {
          path: '/id/?'
        }
        {
          path: '/universe/?'
        }
        {
          path: '/active_date/?'
        }
      ]
      excludedPaths: [
        {
          path: '/*'
        }
      ]
    }
  }
  {
    name: 'guesses'
    partitionKey: '/userId'
    defaultTtl: 7776000 // 90 days TTL for automatic cleanup
    indexingPolicy: {
      indexingMode: 'consistent'
      includedPaths: [
        {
          path: '/userId/?'
        }
        {
          path: '/puzzleId/?'
        }
        {
          path: '/timestamp/?'
        }
      ]
      excludedPaths: [
        {
          path: '/*'
        }
      ]
    }
  }
]

resource containerResources 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2023-04-15' = [for container in containers: {
  parent: database
  name: container.name
  properties: {
    resource: {
      id: container.name
      partitionKey: {
        paths: [
          container.partitionKey
        ]
        kind: 'Hash'
      }
      defaultTtl: container.defaultTtl
      indexingPolicy: container.indexingPolicy
    }
    options: {}
  }
}]

output cosmosAccountName string = cosmosAccount.name
output cosmosEndpoint string = cosmosAccount.properties.documentEndpoint
output cosmosPrimaryKey string = cosmosAccount.listKeys().primaryMasterKey