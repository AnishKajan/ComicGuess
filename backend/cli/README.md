# ComicGuess CLI Tools

Command-line interface tools for managing ComicGuess content including puzzles and character images.

## Installation

1. Install the main backend requirements:
```bash
pip install -r ../requirements.txt
```

2. Install CLI-specific requirements:
```bash
pip install -r requirements.txt
```

3. Set up environment variables (copy from backend/.env.example):
```bash
# Azure Cosmos DB
COSMOS_DB_ENDPOINT=your_cosmos_endpoint
COSMOS_DB_KEY=your_cosmos_key
COSMOS_DB_DATABASE_NAME=comicguess
COSMOS_DB_CONTAINER_USERS=users
COSMOS_DB_CONTAINER_PUZZLES=puzzles
COSMOS_DB_CONTAINER_GUESSES=guesses

# Azure Blob Storage
AZURE_STORAGE_CONNECTION_STRING=your_storage_connection_string
AZURE_STORAGE_CONTAINER_NAME=character-images
```

## Usage

The CLI provides three main tools: `puzzle` for puzzle management, `image` for image management, and `admin` for administrative operations.

### Puzzle Management

#### Import Puzzles

Import puzzles from CSV file:
```bash
python -m cli.main puzzle import puzzles.csv
```

Import puzzles from JSON file:
```bash
python -m cli.main puzzle import puzzles.json
```

Dry run (validate without creating):
```bash
python -m cli.main puzzle import puzzles.csv --dry-run
```

#### Export Puzzles

Export all puzzles to JSON:
```bash
python -m cli.main puzzle export all_puzzles.json
```

Export Marvel puzzles to CSV:
```bash
python -m cli.main puzzle export marvel_puzzles.csv --universe marvel --format csv
```

Export puzzles in date range:
```bash
python -m cli.main puzzle export january_puzzles.json --universe DC --start-date 2024-01-01 --end-date 2024-01-31
```

#### Validate Puzzles

Validate all puzzles:
```bash
python -m cli.main puzzle validate
```

Validate specific universe:
```bash
python -m cli.main puzzle validate --universe marvel
```

#### Delete Puzzles

Delete puzzles in date range (requires confirmation):
```bash
python -m cli.main puzzle delete marvel 2024-01-01 2024-01-31 --confirm
```

### Image Management

#### Upload Single Image

Upload a character image:
```bash
python -m cli.main image upload marvel "Spider-Man" spider-man.jpg
```

Upload without optimization:
```bash
python -m cli.main image upload DC "Batman" batman.png --no-optimize
```

Overwrite existing image:
```bash
python -m cli.main image upload image "Spawn" spawn.jpg --overwrite
```

#### Bulk Upload Images

Upload all images from a directory:
```bash
python -m cli.main image bulk-upload marvel ./images/marvel/
```

Dry run to validate images:
```bash
python -m cli.main image bulk-upload DC ./images/DC/ --dry-run
```

#### List Images

List all images in a universe:
```bash
python -m cli.main image list marvel
```

#### Validate Images

Validate all images:
```bash
python -m cli.main image validate
```

Validate specific universe:
```bash
python -m cli.main image validate --universe DC
```

#### Delete Image

Delete a character image (requires confirmation):
```bash
python -m cli.main image delete marvel "Spider-Man" --confirm
```

### Administrative Operations

#### Database Seeding

Seed database with sample data:
```bash
python -m cli.main admin seed --sample
```

Seed from JSON file:
```bash
python -m cli.main admin seed --file seed_data.json
```

#### Database Backup and Restore

Create backup:
```bash
python -m cli.main admin backup ./backups/
```

Create backup including blob storage:
```bash
python -m cli.main admin backup ./backups/ --include-blobs
```

Restore from backup:
```bash
python -m cli.main admin restore backup_20240115_120000.zip --confirm
```

#### Database Migrations

Run migration (dry run):
```bash
python -m cli.main admin migrate add_user_preferences --dry-run
```

Run actual migration:
```bash
python -m cli.main admin migrate add_user_preferences
```

Available migrations:
- `add_user_preferences`: Add preferences field to users
- `update_puzzle_aliases`: Normalize puzzle character aliases
- `cleanup_old_guesses`: Clean up old guess data

#### Health Check

Perform system health check:
```bash
python -m cli.main admin health
```

## File Formats

### CSV Format for Puzzles

```csv
universe,character,character_aliases,image_key,active_date
marvel,Spider-Man,"Spiderman,Peter Parker",marvel/spider-man.jpg,2024-01-15
DC,Batman,"Bruce Wayne,Dark Knight",DC/batman.jpg,2024-01-16
image,Spawn,"Al Simmons",image/spawn.jpg,2024-01-17
```

### JSON Format for Puzzles

```json
[
  {
    "universe": "marvel",
    "character": "Spider-Man",
    "character_aliases": ["Spiderman", "Peter Parker"],
    "image_key": "marvel/spider-man.jpg",
    "active_date": "2024-01-15"
  },
  {
    "universe": "DC",
    "character": "Batman",
    "character_aliases": ["Bruce Wayne", "Dark Knight"],
    "image_key": "DC/batman.jpg",
    "active_date": "2024-01-16"
  }
]
```

### Seed Data Format

Seed data should be in JSON format with the following structure:

```json
{
  "users": [
    {
      "id": "user1",
      "username": "comic_fan",
      "email": "fan@example.com"
    }
  ],
  "puzzles": [
    {
      "universe": "marvel",
      "character": "Spider-Man",
      "character_aliases": ["Spiderman", "Peter Parker"],
      "image_key": "marvel/spider-man.jpg",
      "active_date": "2024-01-15"
    }
  ],
  "guesses": [
    {
      "user_id": "user1",
      "puzzle_id": "20240115-marvel",
      "guess": "Spider-Man",
      "is_correct": true
    }
  ]
}
```

### Image File Organization

For bulk upload, organize images in directories with character names as filenames:

```
images/
├── marvel/
│   ├── spider-man.jpg
│   ├── iron-man.jpg
│   └── captain-america.jpg
├── DC/
│   ├── batman.jpg
│   ├── superman.jpg
│   └── wonder-woman.jpg
└── image/
    ├── spawn.jpg
    ├── invincible.jpg
    └── the-walking-dead.jpg
```

Character names are automatically derived from filenames:
- `spider-man.jpg` → "Spider Man"
- `iron_man.jpg` → "Iron Man"
- `captain-america.jpg` → "Captain America"

## Image Requirements

- **Supported formats**: JPG, JPEG, PNG, WebP
- **Maximum file size**: 10MB
- **Minimum dimensions**: 100x100 pixels
- **Maximum dimensions**: 4000x4000 pixels
- **Optimization**: Images are automatically optimized for web delivery (JPEG, 85% quality)

## Error Handling

The CLI tools provide detailed error reporting:

- **Validation errors**: Invalid data format, missing required fields
- **Duplicate detection**: Prevents creating duplicate puzzles for the same date/universe
- **File errors**: Missing files, unsupported formats, file size limits
- **Network errors**: Database connection issues, blob storage problems

## Examples

### Complete Workflow Example

1. Prepare puzzle data in CSV format
2. Validate the data:
   ```bash
   python -m cli.main puzzle import puzzles.csv --dry-run
   ```
3. Import the puzzles:
   ```bash
   python -m cli.main puzzle import puzzles.csv
   ```
4. Upload character images:
   ```bash
   python -m cli.main image bulk-upload marvel ./images/marvel/
   ```
5. Validate everything:
   ```bash
   python -m cli.main puzzle validate
   python -m cli.main image validate
   ```

### Maintenance Tasks

Export backup of all puzzles:
```bash
python -m cli.main puzzle export backup_$(date +%Y%m%d).json
```

Clean up test data:
```bash
python -m cli.main puzzle delete marvel 2024-01-01 2024-01-31 --confirm
```

Check image accessibility:
```bash
python -m cli.main image validate --universe marvel
```

Create database backup:
```bash
python -m cli.main admin backup ./backups/
```

Perform health check:
```bash
python -m cli.main admin health
```

## Troubleshooting

### Common Issues

1. **Database connection errors**: Verify Cosmos DB credentials and network connectivity
2. **Blob storage errors**: Check Azure Storage connection string and container permissions
3. **Image processing errors**: Ensure Pillow is installed and images are valid
4. **Permission errors**: Verify Azure service permissions for read/write operations

### Debug Mode

Set environment variable for detailed logging:
```bash
export PYTHONPATH=..
export LOG_LEVEL=DEBUG
python -m cli.main puzzle validate
```

### Performance Tips

- Use `--dry-run` to validate large datasets before importing
- Process images in smaller batches for better error handling
- Use image optimization to reduce storage costs and improve performance
- Export data regularly for backup purposes