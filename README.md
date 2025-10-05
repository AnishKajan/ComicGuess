# ComicGuess

A daily Wordle-style puzzle web application where users guess comic book characters from Marvel, DC, and Image Comics universes.

## Project Structure

```
ComicGuess/
├── frontend/          # Next.js 15 frontend application
├── functions/         # Firebase Cloud Functions (TypeScript)
├── backend/           # Legacy FastAPI backend (deprecated)
├── .kiro/            # Kiro specifications and configuration
└── README.md         # This file
```

## Features

- Daily puzzles for Marvel, DC, and Image Comics universes
- Universe-specific theming (red, blue, black)
- Streak tracking and statistics
- Responsive mobile-first design
- Character image reveals on successful guesses
- Firebase Authentication integration
- Serverless architecture with Cloud Functions

## Tech Stack

### Frontend
- **Next.js 15** with App Router
- **TypeScript** for type safety
- **Tailwind CSS** for styling
- **React** for UI components
- **Firebase SDK** for auth and data

### Backend (Firebase-only)
- **Firebase Cloud Functions** for serverless API
- **Firebase Firestore** for data storage
- **Firebase Storage** for character images
- **Firebase Authentication** for user management
- **Cloud Scheduler** for daily puzzle rotation

### Infrastructure
- **Firebase Hosting** for static site hosting
- **Firebase Security Rules** for data protection
- **Scheduled Cloud Functions** for automation

## Getting Started

### Prerequisites

- Node.js 20+ and npm
- Firebase CLI (`npm install -g firebase-tools`)
- Firebase project with Blaze plan (for Cloud Functions)

### Firebase Setup

1. **Initialize Firebase project:**
   ```bash
   firebase login
   firebase use --add  # Select your Firebase project
   ```

2. **Enable required services:**
   - Firestore Database
   - Firebase Authentication
   - Firebase Storage
   - Cloud Functions
   - Firebase Hosting

### Frontend Setup

```bash
cd frontend
npm install
# Environment variables are already configured in .env.local
npm run dev
```

The frontend will be available at `http://localhost:3000`

### Functions Setup

```bash
cd functions
npm install
npm run build
```

### Local Development with Emulators

```bash
# Start Firebase emulators (run from project root)
firebase emulators:start

# In another terminal, start frontend
cd frontend && npm run dev
```

## Development

### Frontend Development
- `npm run dev` - Start development server
- `npm run build` - Build for production
- `npm run lint` - Run ESLint
- `npm run type-check` - Run TypeScript checks

### Functions Development
- `npm run build` - Compile TypeScript
- `npm run build:watch` - Watch mode compilation
- `firebase emulators:start --only functions` - Test functions locally

## Daily Puzzle Rotation

The daily puzzles are automatically rotated by a Cloud Function (`rotateDailyPuzzle`) that:

1. **Runs daily at midnight EST/EDT** using Cloud Scheduler
2. **Deterministically selects characters** for each publisher using a date-based hash
3. **Creates puzzle documents** in Firestore at `puzzles/{yyyy-mm-dd}-{publisher}`
4. **Ensures consistent puzzles** - the same date always produces the same character

### Switching to Curated Puzzles

To use pre-selected characters instead of deterministic selection:

1. Create a `curatedPuzzles` collection in Firestore
2. Add documents with date keys and character IDs
3. Update the `rotateDailyPuzzle` function to query this collection
4. See comments in `functions/src/index.ts` for implementation details

## Environment Variables

### Frontend (.env.local)
The Firebase configuration is already set up in `frontend/.env.local`:
- `NEXT_PUBLIC_FIREBASE_API_KEY` - Firebase web API key
- `NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN` - Firebase auth domain
- `NEXT_PUBLIC_FIREBASE_PROJECT_ID` - Firebase project ID
- `NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET` - Firebase storage bucket
- `NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID` - Firebase messaging sender ID
- `NEXT_PUBLIC_FIREBASE_APP_ID` - Firebase app ID
- `NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID` - Firebase analytics measurement ID

## Deployment

### Deploy Functions
```bash
# Build and deploy Cloud Functions
cd functions
npm run build
firebase deploy --only functions
```

### Deploy Frontend
```bash
# Build and deploy to Firebase Hosting
cd frontend
npm run build:static
firebase deploy --only hosting
```

### Deploy Everything
```bash
# Deploy all Firebase services
firebase deploy
```

## Data Seeding

### Seed Character Data

1. **Prepare character data** in `functions/src/seedCharacters.ts`
2. **Run the seeding script:**
   ```bash
   cd functions
   npm run build
   node lib/seedCharacters.js
   ```

### Character Data Structure

Characters should be stored in Firestore with this structure:
```typescript
{
  id: string;           // Unique character ID
  name: string;         // Character display name
  publisher: "marvel" | "dc" | "image";
  realName?: string;    // Character's real name
  imageUrl?: string;    // Path to character image
  description?: string; // Character description
}
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Submit a pull request

## License

This project is licensed under the MIT License.