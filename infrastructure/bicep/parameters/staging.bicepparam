using '../main.bicep'

param environment = 'staging'
param location = 'eastus'
param appName = 'comicguess'
param tags = {
  application: 'ComicGuess'
  environment: 'staging'
  managedBy: 'bicep'
  costCenter: 'staging'
  owner: 'dev-team'
}