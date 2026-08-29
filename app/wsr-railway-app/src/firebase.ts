// Firebase initialisation.
//
// Configured through VITE_FIREBASE_* variables. When they are absent the
// app still runs on the static timetable — verification is simply hidden
// rather than throwing — so the public site needs no backend at all.
//
// Point at the local emulator by setting VITE_FIRESTORE_EMULATOR, e.g.
//   VITE_FIREBASE_PROJECT_ID=demo-wsr VITE_FIRESTORE_EMULATOR=localhost:8085

import { initializeApp, type FirebaseApp } from 'firebase/app';
import {
  connectAuthEmulator,
  getAuth,
  GoogleAuthProvider,
  type Auth,
} from 'firebase/auth';
import { connectFirestoreEmulator, getFirestore, type Firestore } from 'firebase/firestore';

const config = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
};

const emulator = import.meta.env.VITE_FIRESTORE_EMULATOR as string | undefined;
const authEmulator = import.meta.env.VITE_AUTH_EMULATOR as string | undefined;

export const isFirebaseConfigured = Boolean(config.projectId);

let app: FirebaseApp | null = null;
let firestore: Firestore | null = null;
let firebaseAuth: Auth | null = null;

if (isFirebaseConfigured) {
  // A failure here must not take the whole site down — the timetable does
  // not need Firebase, so degrade to "verification unavailable" instead.
  try {
    app = initializeApp(config);
    firestore = getFirestore(app);
    if (emulator) {
      const [host, port] = emulator.split(':');
      connectFirestoreEmulator(firestore, host, Number(port));
    }
  } catch (error) {
    console.error('Firestore unavailable; verification disabled', error);
    firestore = null;
  }

  try {
    firebaseAuth = getAuth(app!);
    if (authEmulator) {
      connectAuthEmulator(firebaseAuth, `http://${authEmulator}`, { disableWarnings: true });
    }
  } catch (error) {
    console.error('Auth unavailable; verification is read-only', error);
    firebaseAuth = null;
  }
}

export const db = firestore;
export const auth = firebaseAuth;
export const googleProvider = new GoogleAuthProvider();
