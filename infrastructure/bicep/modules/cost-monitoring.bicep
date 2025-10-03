@description('Cost monitoring and budget management for ComicGuess application')
param resourceGroupName string
param subscriptionId string
param budgetAmount int = 100
param alertThresholds array = [50, 75, 90, 100]
param contactEmails array
param environment string

// Budget for the resource group
resource budget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: 'comicguess-${environment}-budget'
  properties: {
    timePeriod: {
      startDate: '2024-01-01'
      endDate: '2025-12-31'
    }
    timeGrain: 'Monthly'
    amount: budgetAmount
    category: 'Cost'
    filter: {
      dimensions: {
        name: 'ResourceGroupName'
        operator: 'In'
        values: [
          resourceGroupName
        ]
      }
    }
    notifications: {
      for threshold in alertThresholds: {
        'alert${threshold}': {
          enabled: true
          operator: 'GreaterThan'
          threshold: threshold
          contactEmails: contactEmails
          contactRoles: [
            'Owner'
            'Contributor'
          ]
          thresholdType: 'Actual'
        }
      }
    }
  }
}

// Cost anomaly detector
resource costAnomalyDetector 'Microsoft.CostManagement/scheduledActions@2023-08-01' = {
  name: 'comicguess-${environment}-anomaly-detector'
  kind: 'Email'
  properties: {
    displayName: 'ComicGuess Cost Anomaly Detection'
    fileDestination: {
      fileFormats: [
        'Csv'
      ]
    }
    notification: {
      to: contactEmails
      subject: 'ComicGuess Cost Anomaly Detected - ${environment}'
      message: 'Unusual spending pattern detected for ComicGuess ${environment} environment'
    }
    schedule: {
      frequency: 'Daily'
      hourOfDay: 9
      daysOfWeek: [
        'Monday'
        'Tuesday'
        'Wednesday'
        'Thursday'
        'Friday'
      ]
    }
    status: 'Enabled'
    viewId: '/subscriptions/${subscriptionId}/resourceGroups/${resourceGroupName}/providers/Microsoft.CostManagement/views/comicguess-cost-view'
  }
}

output budgetId string = budget.id
output anomalyDetectorId string = costAnomalyDetector.id