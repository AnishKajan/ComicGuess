import { FieldValue } from "firebase-admin/firestore";
import { onSchedule } from "firebase-functions/v2/scheduler";
import { onCall, HttpsError } from "firebase-functions/v2/https";
import dayjs from "dayjs";
import tz from "dayjs/plugin/timezone.js";
import utc from "dayjs/plugin/utc.js";
import dayOfYear from "dayjs/plugin/dayOfYear.js";
import { db } from "./firebase.js";

dayjs.extend(utc);
dayjs.extend(tz);
dayjs.extend(dayOfYear);

// ---- TEMP seeder (remove after run) ----
// export { seedCharacters } from "./seedCharacters.js";

// ---- Scheduled daily rotation at midnight America/New_York ----
export const rotateDailyPuzzle = onSchedule(
  {
    schedule: "0 0 * * *",
    timeZone: "America/New_York",
    region: "us-central1"
  },
  async () => {
    const today = dayjs().tz("America/New_York").format("YYYY-MM-DD");
    // Pick a publisher based on day (cycle 3): Marvel/DC/Image
    const publishers = ["Marvel","DC","Image"] as const;
    const publisher = publishers[(dayjs().dayOfYear() % publishers.length)];
    
    // Get characters for publisher
    const snap = await db.collection(`characters/${publisher}/items`).get();
    if (snap.empty) {
      console.warn(`No characters to choose for ${publisher}`);
      return;
    }
    // Rotate deterministically by day-of-year
    const idx = dayjs().dayOfYear() % snap.size;
    const chosen = snap.docs[idx];
    
    await db.doc(`puzzles/${today}`).set({
      date: today,
      publisher,
      characterId: chosen.id,
    }, { merge: true });
    
    console.log("Puzzle set:", { today, publisher, characterId: chosen.id });
  });

// ---- Callable: validate guess ----
export const checkGuess = onCall(
  { region: "us-central1" },
  async (request) => {
    const { publisher, guess } = request.data as { publisher: string; guess: string };
    if (!publisher || !guess) {
      throw new HttpsError("invalid-argument", "publisher and guess are required");
    }
    const today = dayjs().tz("America/New_York").format("YYYY-MM-DD");
    const puzzleDoc = await db.doc(`puzzles/${today}`).get();
    if (!puzzleDoc.exists) {
      throw new HttpsError("failed-precondition", "No puzzle set for today");
    }
    const { characterId } = puzzleDoc.data()!;
    const targetDoc = await db.doc(`characters/${publisher}/items/${characterId}`).get();
    if (!targetDoc.exists) {
      return { correct: false, reason: "wrong-publisher" };
    }
    const target = targetDoc.data()!;
    const normalized = (s: string) => s.toLowerCase().replace(/\s+/g, "");
    const correct = normalized(target.name) === normalized(guess);
    
    // Optional: record user guess if authed
    if (request.auth?.uid) {
      await db
        .collection(`users/${request.auth.uid}/guesses`)
        .doc(today)
        .set({
          ts: FieldValue.serverTimestamp(),
          publisher,
          guess,
          correct,
          characterId,
        }, { merge: true });
    }
    
    return {
      correct,
      characterId: correct ? characterId : undefined,
      meta: correct ? target.meta ?? {} : undefined,
    };
  });

