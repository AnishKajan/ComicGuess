using '../main.bicep'

param environment = 'dev'
param location = 'eastus'
param appName = 'comicguess'
param tags = {
  application: 'ComicGuess'
  environment: 'dev'
  managedBy: 'bicep'
  costCenter: 'development'
  owner: 'dev-team'
}