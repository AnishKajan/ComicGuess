import { initializeApp, getApps } from "firebase-admin/app";
import { getFirestore } from "firebase-admin/firestore";

// Initialize Firebase Admin only once
if (getApps().length === 0) {
  initializeApp();
}

export const db = getFirestore();