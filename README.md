# ComicGuess

A daily Wordle-style puzzle web application where users guess comic book characters from Marvel, DC, and Image Comics universes.

## Project Structure

```
ComicGuess/
├── frontend/          # Next.js 14 frontend application
├── backend/           # FastAPI backend application
├── .kiro/            # Kiro specifications and configuration
└── README.md         # This file
```

## Features

- Daily puzzles for Marvel, DC, and Image Comics universes
- Universe-specific theming (red, blue, black)
- Streak tracking and statistics
- Responsive mobile-first design
- Character image reveals on successful guesses

## Tech Stack

### Frontend
- **Next.js 14** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **React** for UI components

### Backend
- **FastAPI** for high-performance API
- **Python 3.11+** with async/await
- **Pydantic** for data validation
- **JWT** for authentication

### Infrastructure
- **Firebase Firestore** for data storage
- **Firebase Storage** for character images
- **Cloudflare CDN** for content delivery
- **Scheduled tasks** for daily puzzle automation

## Getting Started

### Prerequisites

- Node.js 18+ and npm
- Python 3.11+
- Firebase project (for cloud services)

### Frontend Setup

```bash
cd frontend
npm install
cp .env.local.example .env.local
# Edit .env.local with your configuration
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your configuration
python main.py
```

The backend API will be available at `http://localhost:8000`

## Development

### Frontend Development
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript checks

### Backend Development
- `python main.py` - Start development server
- `pytest` - Run tests
- `pytest --cov` - Run tests with coverage

## API Documentation

Once the backend is running, visit `http://localhost:8000/docs` for interactive API documentation.

## Environment Variables

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL` - Backend API URL
- `NEXT_PUBLIC_JWT_SECRET` - JWT secret for client-side validation

### Backend (.env)
- `FIREBASE_PROJECT_ID` - Firebase project ID
- `FIREBASE_PRIVATE_KEY` - Firebase service account private key
- `FIREBASE_CLIENT_EMAIL` - Firebase service account email
- `JWT_SECRET_KEY` - JWT signing secret

## Deploy (manual)

```bash
cd frontend
npm ci
npm run build:static
npx firebase deploy --only hosting --project comicguess
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License.