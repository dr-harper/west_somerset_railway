# Firebase Integration Guide

This guide shows how to replace the mock data with actual Firestore queries.

## 1. Initialize Firebase

Create `src/lib/firebase/config.ts`:

```typescript
import { initializeApp } from 'firebase/app';
import { getFirestore } from 'firebase/firestore';
import { getAuth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: process.env.VITE_FIREBASE_API_KEY,
  authDomain: process.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: process.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: process.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: process.env.VITE_FIREBASE_APP_ID
};

const app = initializeApp(firebaseConfig);
export const db = getFirestore(app);
export const auth = getAuth(app);
```

## 2. Replace Mock Data Queries

### Get All Stations

**Current (Mock):**
```typescript
// In trainService.ts
async getAllStations(): Promise<Station[]> {
  return Promise.resolve(Array.from(this.stations.values()));
}
```

**Replace with Firestore:**
```typescript
import { collection, getDocs } from 'firebase/firestore';
import { db } from '../lib/firebase/config';

async getAllStations(): Promise<Station[]> {
  const stationsRef = collection(db, 'stations');
  const snapshot = await getDocs(stationsRef);
  return snapshot.docs.map(doc => doc.data() as Station);
}
```

### Get Today's Trains

**Current (Mock):**
```typescript
async getActiveTrains(): Promise<Train[]> {
  const trains = Array.from(this.trains.values()).filter(train => {
    return train.status.state === 'Running' || train.status.state === 'Scheduled';
  });
  return Promise.resolve(trains);
}
```

**Replace with Firestore:**
```typescript
import { collection, query, where, getDocs } from 'firebase/firestore';

async getActiveTrains(): Promise<Train[]> {
  const today = new Date().toISOString().split('T')[0];
  const trainsRef = collection(db, `schedules/${today}/trains`);
  const q = query(
    trainsRef,
    where('status.state', 'in', ['Running', 'Scheduled'])
  );
  const snapshot = await getDocs(q);
  return snapshot.docs.map(doc => doc.data() as Train);
}
```

### Get Train by ID

**Current (Mock):**
```typescript
async getTrainById(id: string): Promise<Train | null> {
  return Promise.resolve(this.trains.get(id) || null);
}
```

**Replace with Firestore:**
```typescript
import { doc, getDoc } from 'firebase/firestore';

async getTrainById(id: string): Promise<Train | null> {
  const today = new Date().toISOString().split('T')[0];
  const trainRef = doc(db, `schedules/${today}/trains`, id);
  const trainDoc = await getDoc(trainRef);
  return trainDoc.exists() ? trainDoc.data() as Train : null;
}
```

### Real-time Train Updates

**Current (Mock):**
```typescript
onTrainUpdate(trainId: string, callback: (train: Train) => void): () => void {
  const key = `train:${trainId}`;
  if (!this.listeners.has(key)) {
    this.listeners.set(key, new Set());
  }
  this.listeners.get(key)!.add(callback);
  return () => {
    this.listeners.get(key)?.delete(callback);
  };
}
```

**Replace with Firestore:**
```typescript
import { doc, onSnapshot } from 'firebase/firestore';

onTrainUpdate(trainId: string, callback: (train: Train) => void): () => void {
  const today = new Date().toISOString().split('T')[0];
  const trainRef = doc(db, `schedules/${today}/trains`, trainId);
  
  const unsubscribe = onSnapshot(trainRef, (doc) => {
    if (doc.exists()) {
      callback(doc.data() as Train);
    }
  });
  
  return unsubscribe;
}
```

### Real-time Position Updates

**Current (Mock):**
```typescript
// Simulated position updates
private updateTrainPositions() {
  // ... simulation code
}
```

**Replace with Firestore:**
```typescript
import { doc, onSnapshot } from 'firebase/firestore';

subscribeToTrainPosition(trainId: string, callback: (position: any) => void): () => void {
  const positionRef = doc(db, 'realtime/positions', trainId);
  
  const unsubscribe = onSnapshot(positionRef, (doc) => {
    if (doc.exists()) {
      callback(doc.data());
    }
  });
  
  return unsubscribe;
}
```

## 3. Loading Data into Firestore

Use this script to populate Firestore with sample data:

```typescript
// scripts/populateFirestore.ts
import { doc, setDoc, collection, writeBatch } from 'firebase/firestore';
import { db } from '../lib/firebase/config';
import { FIRESTORE_STATIONS, FIRESTORE_TRAINS } from '../data/sampleFirestoreData';

async function populateStations() {
  const batch = writeBatch(db);
  
  Object.entries(FIRESTORE_STATIONS).forEach(([code, station]) => {
    const stationRef = doc(db, 'stations', code);
    batch.set(stationRef, station);
  });
  
  await batch.commit();
  console.log('Stations populated');
}

async function populateTrains() {
  const today = new Date().toISOString().split('T')[0];
  const batch = writeBatch(db);
  
  Object.entries(FIRESTORE_TRAINS).forEach(([id, train]) => {
    const trainRef = doc(db, `schedules/${today}/trains`, id);
    batch.set(trainRef, train);
  });
  
  await batch.commit();
  console.log('Trains populated');
}

// Run the population
populateStations();
populateTrains();
```

## 4. Departure Board Query

**Current (Mock):**
```typescript
async getDepartureBoard(stationCode: StationCode, limit = 10): Promise<DepartureBoard> {
  // ... complex logic to generate from trains
}
```

**Replace with Firestore (Option 1 - Client-side):**
```typescript
async getDepartureBoard(stationCode: StationCode, limit = 10): Promise<DepartureBoard> {
  const today = new Date().toISOString().split('T')[0];
  const currentTime = new Date().toTimeString().slice(0, 5);
  
  // Get all trains for today
  const trainsRef = collection(db, `schedules/${today}/trains`);
  const snapshot = await getDocs(trainsRef);
  const trains = snapshot.docs.map(doc => doc.data() as Train);
  
  // Filter and sort departures
  const departures: Departure[] = [];
  
  trains.forEach(train => {
    const stop = train.stops.find(s => s.stationCode === stationCode);
    if (stop && stop.scheduledDeparture && stop.scheduledDeparture >= currentTime) {
      departures.push({
        trainId: train.id,
        serviceId: train.serviceId,
        time: stop.scheduledDeparture,
        destination: train.stops[train.stops.length - 1].stationName,
        platform: stop.platform,
        status: stop.delayMinutes ? `${stop.delayMinutes} min late` : 'On Time',
        serviceType: train.serviceType,
        delayMinutes: stop.delayMinutes,
        isCancelled: stop.status === 'Cancelled'
      });
    }
  });
  
  departures.sort((a, b) => a.time.localeCompare(b.time));
  
  return {
    station: stationCode,
    generated: new Date(),
    departures: departures.slice(0, limit),
    arrivals: [] // Similar logic for arrivals
  };
}
```

**Replace with Firestore (Option 2 - Cloud Function):**
```typescript
// Cloud Function to generate departure boards
export const getDepartureBoard = functions.https.onCall(async (data) => {
  const { stationCode, limit = 10 } = data;
  // Server-side logic to generate departure board
  // Cache result in Firestore for performance
  return departureBoard;
});

// Client call
import { getFunctions, httpsCallable } from 'firebase/functions';

const functions = getFunctions();
const getDepartureBoard = httpsCallable(functions, 'getDepartureBoard');

async getDepartureBoard(stationCode: StationCode): Promise<DepartureBoard> {
  const result = await getDepartureBoard({ stationCode, limit: 10 });
  return result.data as DepartureBoard;
}
```

## 5. Authentication for Admin

```typescript
// src/contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect } from 'react';
import { auth } from '../lib/firebase/config';
import { signInWithEmailAndPassword, signOut, onAuthStateChanged } from 'firebase/auth';

const AuthContext = createContext({});

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isAdmin, setIsAdmin] = useState(false);
  
  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, async (user) => {
      setUser(user);
      if (user) {
        // Check admin status in Firestore
        const userDoc = await getDoc(doc(db, 'users', user.uid));
        setIsAdmin(userDoc.data()?.isAdmin || false);
      }
    });
    return unsubscribe;
  }, []);
  
  const login = (email: string, password: string) => {
    return signInWithEmailAndPassword(auth, email, password);
  };
  
  const logout = () => signOut(auth);
  
  return (
    <AuthContext.Provider value={{ user, isAdmin, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
```

## 6. Update Train Status (Admin)

```typescript
// Admin function to update train status
async function updateTrainStatus(trainId: string, status: TrainStatus) {
  if (!isAdmin) throw new Error('Unauthorized');
  
  const today = new Date().toISOString().split('T')[0];
  const trainRef = doc(db, `schedules/${today}/trains`, trainId);
  
  await updateDoc(trainRef, {
    status,
    updatedAt: serverTimestamp()
  });
}
```

## 7. Performance Optimization

### Use Firestore Indexes
Create indexes for common queries in Firebase Console:
- `schedules/{date}/trains` - Index on `status.state`
- `schedules/{date}/trains` - Index on `origin` and `destination`

### Cache Departure Boards
```typescript
// Cache departure boards for 1 minute
const departureBoardCache = new Map();

async getDepartureBoard(stationCode: StationCode): Promise<DepartureBoard> {
  const cacheKey = `${stationCode}_${Date.now() / 60000 | 0}`;
  
  if (departureBoardCache.has(cacheKey)) {
    return departureBoardCache.get(cacheKey);
  }
  
  const board = await fetchDepartureBoard(stationCode);
  departureBoardCache.set(cacheKey, board);
  
  // Clear old cache entries
  if (departureBoardCache.size > 20) {
    const firstKey = departureBoardCache.keys().next().value;
    departureBoardCache.delete(firstKey);
  }
  
  return board;
}
```

## 8. Offline Support

```typescript
import { enableNetwork, disableNetwork, enableIndexedDbPersistence } from 'firebase/firestore';

// Enable offline persistence
enableIndexedDbPersistence(db).catch((err) => {
  if (err.code === 'failed-precondition') {
    // Multiple tabs open, persistence can only be enabled in one tab at a time
  } else if (err.code === 'unimplemented') {
    // The current browser doesn't support persistence
  }
});

// Handle online/offline status
window.addEventListener('online', () => enableNetwork(db));
window.addEventListener('offline', () => disableNetwork(db));
```

## Environment Variables

Create `.env.local`:
```env
VITE_FIREBASE_API_KEY=your_api_key
VITE_FIREBASE_AUTH_DOMAIN=your_project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your_project_id
VITE_FIREBASE_STORAGE_BUCKET=your_project.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=your_sender_id
VITE_FIREBASE_APP_ID=your_app_id
```

## Testing

```typescript
// Use Firebase Emulators for local development
import { connectFirestoreEmulator } from 'firebase/firestore';
import { connectAuthEmulator } from 'firebase/auth';

if (import.meta.env.DEV) {
  connectFirestoreEmulator(db, 'localhost', 8080);
  connectAuthEmulator(auth, 'http://localhost:9099');
}
```

Run emulators:
```bash
firebase emulators:start --only firestore,auth
```