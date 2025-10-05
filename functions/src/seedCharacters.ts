/**
 * Script to seed character data into Firestore
 * Run this once to populate the characters collection
 */

import * as admin from "firebase-admin";

// Initialize Firebase Admin SDK
if (!admin.apps.length) {
  admin.initializeApp();
}

const db = admin.firestore();

// Example character data - replace with your actual character data
const sampleCharacters = [
  {
    id: "spider-man",
    name: "Spider-Man",
    publisher: "marvel",
    imageUrl: "/images/characters/spider-man.jpg",
    gender: "Male",
    species: "Human",
    powers: ["Web-slinging", "Wall-crawling", "Spider-sense", "Super strength"],
    teams: ["Avengers", "Fantastic Four"],
    sidekickLegacy: "No",
    alignment: "Hero",
    debutYear: 1962,
  },
  {
    id: "batman",
    name: "Batman",
    publisher: "dc",
    imageUrl: "/images/characters/batman.jpg",
    gender: "Male",
    species: "Human",
    powers: ["Martial arts", "Detective skills", "Gadgets"],
    teams: ["Justice League", "Batman Family"],
    sidekickLegacy: "No",
    alignment: "Hero",
    debutYear: 1939,
  },
  {
    id: "spawn",
    name: "Spawn",
    publisher: "image",
    imageUrl: "/images/characters/spawn.jpg",
    gender: "Male",
    species: "Hellspawn",
    powers: ["Necroplasm", "Chains", "Teleportation", "Immortality"],
    teams: [],
    sidekickLegacy: "No",
    alignment: "Anti-hero",
    debutYear: 1992,
  },
  // Add more characters as needed
];

async function seedCharacters() {
  console.log("Starting character seeding...");
  
  const batch = db.batch();
  
  for (const character of sampleCharacters) {
    const docRef = db.collection("characters").doc(character.id);
    batch.set(docRef, character);
  }
  
  try {
    await batch.commit();
    console.log(`Successfully seeded ${sampleCharacters.length} characters`);
  } catch (error) {
    console.error("Error seeding characters:", error);
    throw error;
  }
}

// Run the seeding function if this file is executed directly
if (require.main === module) {
  seedCharacters()
    .then(() => {
      console.log("Character seeding completed");
      process.exit(0);
    })
    .catch((error) => {
      console.error("Character seeding failed:", error);
      process.exit(1);
    });
}

export { seedCharacters };