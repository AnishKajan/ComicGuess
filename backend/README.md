# ComicGuess Backend API

FastAPI backend for the ComicGuess daily puzzle application.

## Project Structure

```
backend/
├── app/
│   ├── models/        # Pydantic data models
│   ├── services/      # Business logic services
│   ├── repositories/  # Data access layer
│   └── api/          # API endpoint definitions
├── tests/            # Test files
├── main.py           # FastAPI application entry point
├── requirements.txt  # Python dependencies
└── .env.example     # Environment variables template
```

## Setup

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env with your Firebase credentials and configuration
```

4. Run the development server:
```bash
python main.py
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `GET /docs` - Interactive API documentation
- `GET /redoc` - Alternative API documentation

## Testing

Run tests with pytest:
```bash
pytest
pytest --cov  # With coverage report
```

## Environment Variables

See `.env.example` for required environment variables and their descriptions.