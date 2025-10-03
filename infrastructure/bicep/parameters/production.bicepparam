using '../main.bicep'

param environment = 'production'
param location = 'eastus'
param appName = 'comicguess'
param tags = {
  application: 'ComicGuess'
  environment: 'production'
  managedBy: 'bicep'
  costCenter: 'production'
  owner: 'platform-team'
}