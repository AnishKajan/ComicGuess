# Daily Puzzle Generator Azure Function

This Azure Function automatically generates daily comic character puzzles for the ComicGuess application. It runs on a timer trigger at UTC midnight to create new puzzles for Marvel, DC, and Image Comics universes.

## Features

- **Automated Daily Generation**: Timer trigger runs at UTC midnight (0 0 0 * * *)
- **Multi-Universe Support**: Generates puzzles for Marvel, DC, and Image Comics
- **Deterministic Selection**: Uses date-based seeding for consistent character selection
- **Health Monitoring**: Built-in health checks and monitoring endpoints
- **Manual Triggers**: HTTP endpoints for manual puzzle generation and testing
- **Error Handling**: Comprehensive error handling and logging
- **Validation**: Puzzle data integrity validation and duplicate prevention

## Function Endpoints

### Timer Trigger
- **Function**: `daily_puzzle_generator`
- **Schedule**: `0 0 0 * * *` (Daily at UTC midnight)
- **Purpose**: Automatically generate daily puzzles for all universes

### HTTP Endpoints

#### Manual Puzzle Generation
- **Endpoint**: `POST /api/generate-puzzles`
- **Auth Level**: Function key required
- **Parameters**:
  - `date` (optional): Date in YYYY-MM-DD format (defaults to today)
  - `universe` (optional): Specific universe (marvel/dc/image) or all if omitted
- **Purpose**: Manually trigger puzzle generation for testing or recovery

#### Health Check
- **Endpoint**: `GET /api/health`
- **Auth Level**: Anonymous
- **Purpose**: Monitor system health and puzzle availability

## Configuration

### Environment Variables

Required environment variables (set in Azure Function App Configuration or local.settings.json):

```json
{
  "COSMOS_DB_ENDPOINT": "https://your-cosmos-account.documents.azure.com:443/",
  "COSMOS_DB_KEY": "your-cosmos-db-key",
  "COSMOS_DB_DATABASE_NAME": "comicguess",
  "COSMOS_DB_CONTAINER_PUZZLES": "puzzles",
  "AZURE_STORAGE_CONNECTION_STRING": "your-storage-connection-string",
  "AZURE_STORAGE_CONTAINER_NAME": "character-images"
}
```

### Character Pools

Character data is currently embedded in the `puzzle_generator.py` file. In production, this should be moved to:
- Azure Cosmos DB collection
- Azure Blob Storage JSON files
- External configuration service

## Deployment

### Prerequisites
- Azure Functions Core Tools v4
- Python 3.9+
- Azure CLI

### Local Development

1. Clone the repository and navigate to the function directory:
```bash
cd azure-functions/daily-puzzle-generator
```

2. Create a virtual environment:
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy and configure local settings:
```bash
cp local.settings.json.example local.settings.json
# Edit local.settings.json with your Azure credentials
```

5. Run the function locally:
```bash
func start
```

### Azure Deployment

1. Create an Azure Function App:
```bash
az functionapp create \
  --resource-group your-resource-group \
  --consumption-plan-location eastus \
  --runtime python \
  --runtime-version 3.9 \
  --functions-version 4 \
  --name your-function-app-name \
  --storage-account your-storage-account
```

2. Deploy the function:
```bash
func azure functionapp publish your-function-app-name
```

3. Configure application settings:
```bash
az functionapp config appsettings set \
  --name your-function-app-name \
  --resource-group your-resource-group \
  --settings \
    COSMOS_DB_ENDPOINT="your-cosmos-endpoint" \
    COSMOS_DB_KEY="your-cosmos-key" \
    # ... other settings
```

## Testing

Run the test suite:
```bash
pytest test_puzzle_generator.py -v
```

Test specific components:
```bash
# Test character selection
pytest test_puzzle_generator.py::TestPuzzleGeneratorService::test_select_character_for_date_deterministic -v

# Test puzzle generation
pytest test_puzzle_generator.py::TestPuzzleGeneratorService::test_generate_puzzle_for_universe_success -v

# Test health checks
pytest test_puzzle_generator.py::TestPuzzleGeneratorService::test_perform_health_check_healthy -v
```

## Monitoring

### Health Checks
The function provides comprehensive health monitoring:

```bash
# Check system health
curl https://your-function-app.azurewebsites.net/api/health

# Manual puzzle generation
curl -X POST "https://your-function-app.azurewebsites.net/api/generate-puzzles?date=2024-01-15" \
  -H "x-functions-key: your-function-key"
```

### Logging
The function uses structured logging with Azure Application Insights integration:
- Function execution logs
- Puzzle generation results
- Error tracking and alerting
- Performance metrics

### Alerts
Configure Azure Monitor alerts for:
- Function execution failures
- Missing daily puzzles
- Database connectivity issues
- Character pool validation errors

## Character Pool Management

### Current Structure
```python
{
  "marvel": [
    {
      "character": "Spider-Man",
      "aliases": ["Spidey", "Peter Parker", "Web-Slinger"],
      "image_key": "marvel/spider-man.jpg"
    }
  ],
  "dc": [...],
  "image": [...]
}
```

### Future Enhancements
- Move character data to Cosmos DB
- Implement character pool management API
- Add character popularity weighting
- Support for seasonal/themed character rotations
- Dynamic character pool updates

## Error Handling

The function implements comprehensive error handling:

1. **Database Errors**: Retry logic with exponential backoff
2. **Character Selection Errors**: Fallback to default characters
3. **Duplicate Puzzles**: Skip creation and log warning
4. **Validation Errors**: Detailed error reporting and alerting

## Security

- Function key authentication for manual triggers
- Azure Key Vault integration for secrets
- Managed identity for Azure service authentication
- Input validation and sanitization
- Audit logging for all operations

## Performance

- Optimized for minimal cold start time
- Efficient database queries with proper indexing
- Parallel puzzle generation for multiple universes
- Connection pooling and resource reuse

## Troubleshooting

### Common Issues

1. **Missing Puzzles**: Check health endpoint and function logs
2. **Database Connection**: Verify Cosmos DB credentials and network access
3. **Character Selection**: Ensure character pools are properly loaded
4. **Timer Not Triggering**: Check function app configuration and time zone settings

### Debug Commands
```bash
# Check function status
az functionapp show --name your-function-app --resource-group your-rg

# View function logs
az functionapp log tail --name your-function-app --resource-group your-rg

# Test manual generation
curl -X POST "https://your-function-app.azurewebsites.net/api/generate-puzzles" \
  -H "x-functions-key: your-key"
```