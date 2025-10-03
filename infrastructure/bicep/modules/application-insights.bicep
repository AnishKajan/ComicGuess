// Application Insights module
@description('Application Insights name')
param name string

@description('Location for Application Insights')
param location string

@description('Environment name')
param environment string

@description('Tags to apply to resources')
param tags object = {}

// Log Analytics Workspace
resource logAnalyticsWorkspace 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: '${name}-workspace'
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: environment == 'production' ? 365 : 90
    features: {
      searchVersion: 1
      legacy: 0
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

// Application Insights
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: name
  location: location
  tags: tags
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalyticsWorkspace.id
    IngestionMode: 'LogAnalytics'
    publicNetworkAccessForIngestion: 'Enabled'
    publicNetworkAccessForQuery: 'Enabled'
    RetentionInDays: environment == 'production' ? 365 : 90
  }
}

// Alert Rules for production
resource alertRules 'Microsoft.Insights/metricAlerts@2018-03-01' = [for (alert, index) in (environment == 'production' ? [
  {
    name: 'High Error Rate'
    description: 'Alert when error rate exceeds 5%'
    severity: 2
    enabled: true
    scopes: [
      applicationInsights.id
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ErrorRate'
          metricName: 'requests/failed'
          operator: 'GreaterThan'
          threshold: 5
          timeAggregation: 'Average'
        }
      ]
    }
  }
  {
    name: 'High Response Time'
    description: 'Alert when response time exceeds 2 seconds'
    severity: 3
    enabled: true
    scopes: [
      applicationInsights.id
    ]
    evaluationFrequency: 'PT1M'
    windowSize: 'PT5M'
    criteria: {
      'odata.type': 'Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria'
      allOf: [
        {
          name: 'ResponseTime'
          metricName: 'requests/duration'
          operator: 'GreaterThan'
          threshold: 2000
          timeAggregation: 'Average'
        }
      ]
    }
  }
] : []): {
  name: '${name}-${alert.name}'
  location: 'global'
  tags: tags
  properties: {
    description: alert.description
    severity: alert.severity
    enabled: alert.enabled
    scopes: alert.scopes
    evaluationFrequency: alert.evaluationFrequency
    windowSize: alert.windowSize
    criteria: alert.criteria
    actions: []
  }
}]

// Outputs
output id string = applicationInsights.id
output name string = applicationInsights.name
output instrumentationKey string = applicationInsights.properties.InstrumentationKey
output connectionString string = applicationInsights.properties.ConnectionString
output workspaceId string = logAnalyticsWorkspace.id