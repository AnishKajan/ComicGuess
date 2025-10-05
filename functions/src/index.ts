import {onSchedule} from "firebase-functions/v2/scheduler";
import {onCall, HttpsError} from "firebase-functions/v2/https";
import * as admin from "firebase-admin";

// Initialize Firebase Admin SDK
admin.initializeApp();
const db = admin.firestore();

/**
 * Scheduled function to rotate daily puzzles at midnight America/New_York
 * Runs daily at 00:00 EST/EDT
 */
export const rotateDailyPuzzle = onSchedule(
  {
    schedule: "0 0 * * *",
    timeZone: "America/New_York",
  },
  async (event) => {
    const today = new Date();
    const dateStr = today.toISOString().split("T")[0]; // YYYY-MM-DD format
    
    const publishers = ["marvel", "dc", "image"] as const;
    
    try {
      for (const publisher of publishers) {
        // Get all characters for this publisher
        const charactersSnapshot = await db
          .collection("characters")
          .where("publisher", "==", publisher)
          .get();
        
        if (charactersSnapshot.empty) {
          console.warn(`No characters found for publisher: ${publisher}`);
          continue;
        }
        
        const characters = charactersSnapshot.docs;
        
        // Deterministic selection based on date hash
        // This ensures the same character is selected for the same date
        const dateHash = hashString(`${dateStr}-${publisher}`);
        const selectedIndex = dateHash % characters.length;
        const selectedCharacter = characters[selectedIndex];
        
        // Create puzzle document
        const puzzleId = `${dateStr}-${publisher}`;
        const puzzleData = {
          publisher,
          answerId: selectedCharacter.id,
          createdAt: admin.firestore.FieldValue.serverTimestamp(),
          date: dateStr,
        };
        
        await db.collection("puzzles").doc(puzzleId).set(puzzleData);
        
        console.log(`Created puzzle ${puzzleId} with character ${selectedCharacter.id}`);
        
        // TODO: If you want to use a curated list instead of deterministic selection,
        // replace the hash-based selection above with:
        // 1. Maintain a separate collection "curatedPuzzles" with pre-selected characters
        // 2. Query for today's curated puzzle: db.collection("curatedPuzzles").doc(dateStr).get()
        // 3. Use the curatedPuzzle.characterId as answerId
      }
      
      console.log(`Successfully rotated puzzles for ${dateStr}`);
    } catch (error) {
      console.error("Error rotating daily puzzles:", error);
      throw error;
    }
  });

/**
 * Callable function to validate and record a user guess
 * Requires authentication
 */
export const checkGuess = onCall(async (request) => {
  // Require authentication
  if (!request.auth) {
    throw new HttpsError(
      "unauthenticated",
      "The function must be called while authenticated."
    );
  }
  
  const { publisher, guessId } = request.data;
  const uid = request.auth.uid;
  
  // Validate input
  if (!publisher || !guessId) {
    throw new HttpsError(
      "invalid-argument",
      "Missing required parameters: publisher and guessId"
    );
  }
  
  if (!["marvel", "dc", "image"].includes(publisher)) {
    throw new HttpsError(
      "invalid-argument",
      "Invalid publisher. Must be 'marvel', 'dc', or 'image'"
    );
  }
  
  try {
    const today = new Date().toISOString().split("T")[0]; // YYYY-MM-DD
    const puzzleId = `${today}-${publisher}`;
    
    // Get today's puzzle
    const puzzleDoc = await db.collection("puzzles").doc(puzzleId).get();
    
    if (!puzzleDoc.exists) {
      throw new HttpsError(
        "not-found",
        `No puzzle found for ${publisher} on ${today}`
      );
    }
    
    const puzzle = puzzleDoc.data()!;
    const isCorrect = guessId === puzzle.answerId;
    
    // Create guess record
    const datePublisher = `${today}-${publisher}`;
    const guessData = {
      uid,
      publisher,
      guessId,
      correct: isCorrect,
      ts: admin.firestore.FieldValue.serverTimestamp(),
    };
    
    // Store guess under user's guess collection
    await db
      .collection("guesses")
      .doc(uid)
      .collection("days")
      .doc(datePublisher)
      .collection("items")
      .add(guessData);
    
    // Prepare response
    const response: any = {
      correct: isCorrect,
    };
    
    // Only include answer if guess was correct
    if (isCorrect) {
      response.answerId = puzzle.answerId;
    }
    
    return response;
  } catch (error) {
    console.error("Error checking guess:", error);
    
    if (error instanceof HttpsError) {
      throw error;
    }
    
    throw new HttpsError(
      "internal",
      "An internal error occurred while processing the guess"
    );
  }
});

/**
 * Simple hash function for deterministic character selection
 * @param str String to hash
 * @returns Hash number
 */
function hashString(str: string): number {
  let hash = 0;
  for (let i = 0; i < str.length; i++) {
    const char = str.charCodeAt(i);
    hash = ((hash << 5) - hash) + char;
    hash = hash & hash; // Convert to 32-bit integer
  }
  return Math.abs(hash);
}