# Train-Centric Data Model Plan

## Current State Analysis

The app currently uses a **station-centric** approach where:
- Timetables are organized by station codes
- Each station has a list of departure times
- Trains are generated from timetable data
- Difficult to track individual train journeys

## Proposed Train-Centric Model

### Core Concept
**Trains are the primary entities**, with each train having:
- Unique identifier
- Complete journey information
- All stops with arrival/departure times
- Real-time status tracking capability

### Benefits
1. **Better represents reality** - Trains move through stations, not vice versa
2. **Easier real-time tracking** - Update one train object vs multiple station records
3. **Journey visualization** - Complete train path is immediately available
4. **Efficient queries** - Both train and station views from same data

## Data Structure Design

### Primary Data: Trains Collection

```typescript
interface Train {
  // Identity
  id: string;                    // "2A15" (headcode format)
  serviceId: string;             // "NB_1015_BL_MIN" (unique service identifier)
  
  // Schedule Information
  scheduledDate: Date;           // Operating date
  origin: StationCode;           // "BL"
  destination: StationCode;      // "MIN"
  
  // Service Details
  serviceType: 'Steam' | 'Diesel' | 'DMU';
  operator?: string;             // "West Somerset Railway"
  
  // Real-time Status
  status: TrainStatus;
  currentLocation?: {
    between?: [StationCode, StationCode];  // ["WIL", "DON"]
    at?: StationCode;                       // "DON"
    lastUpdated: Date;
  };
  
  // Journey Details
  stops: TrainStop[];
}

interface TrainStop {
  stationCode: string;          // "DON"
  stationName: string;          // "Doniford Halt"
  
  // Times
  scheduledArrival?: string;    // "10:54" (null for origin)
  scheduledDeparture?: string;  // "10:55" (null for destination)
  actualArrival?: string;       // Real-time update
  actualDeparture?: string;     // Real-time update
  
  // Stop Details
  platform?: string;            // "1"
  isRequestStop: boolean;       // true/false
  stopType: 'Origin' | 'Stop' | 'Destination';
  
  // Status
  status: 'Scheduled' | 'Arrived' | 'Departed' | 'Skipped' | 'Cancelled';
  delay?: number;               // Minutes late (+) or early (-)
}

interface TrainStatus {
  state: 'Scheduled' | 'Running' | 'Completed' | 'Cancelled' | 'Terminated';
  delayMinutes: number;         // Overall delay
  message?: string;             // "Running 5 minutes late due to..."
  lastUpdated: Date;
}
```

### Secondary Data: Stations Collection

```typescript
interface Station {
  code: string;                  // "DON"
  name: string;                  // "Doniford Halt"
  
  // Location
  coordinates: {
    lat: number;
    lng: number;
  };
  milepost: number;             // Distance from Bishops Lydeard
  
  // Facilities
  facilities: string[];         // ["Parking", "Toilets", "Cafe"]
  isRequestStop: boolean;
  hasPlatform: boolean;
  
  // Cached departure board (generated from trains)
  departures?: DepartureBoard;
}

interface DepartureBoard {
  station: StationCode;
  generated: Date;
  departures: Departure[];
}

interface Departure {
  trainId: string;              // Reference to train
  time: string;                 // "10:54"
  destination: string;          // "Minehead"
  platform?: string;            // "1"
  status: string;               // "On Time" | "Exp 10:59"
  serviceType: string;          // "Steam"
}
```

## Query Patterns

### 1. Currently Running Trains
```typescript
// Get all trains currently in service
function getActiveTrains(): Train[] {
  return trains.filter(train => 
    train.status.state === 'Running' &&
    train.scheduledDate === today
  );
}
```

### 2. Station Departure Board
```typescript
// Get next departures from a station
function getStationDepartures(stationCode: string, limit = 5): Departure[] {
  const now = getCurrentTime();
  
  return trains
    .flatMap(train => 
      train.stops
        .filter(stop => 
          stop.stationCode === stationCode &&
          stop.scheduledDeparture > now &&
          stop.status !== 'Cancelled'
        )
        .map(stop => ({
          trainId: train.id,
          time: stop.scheduledDeparture,
          destination: train.destination,
          platform: stop.platform,
          status: formatStatus(stop),
          serviceType: train.serviceType
        }))
    )
    .sort((a, b) => a.time.localeCompare(b.time))
    .slice(0, limit);
}
```

### 3. Train Journey Details
```typescript
// Get complete journey for a train
function getTrainJourney(trainId: string): TrainJourney {
  const train = trains.find(t => t.id === trainId);
  return {
    train,
    progress: calculateProgress(train),
    nextStop: getNextStop(train),
    previousStop: getPreviousStop(train)
  };
}
```

### 4. Live Train Map
```typescript
// Get positions of all active trains
function getTrainPositions(): TrainPosition[] {
  return getActiveTrains().map(train => ({
    trainId: train.id,
    position: calculatePosition(train),
    direction: train.origin < train.destination ? 'North' : 'South',
    delay: train.status.delayMinutes
  }));
}
```

## Mock Data Generation Strategy

### Phase 1: Static Schedule (Current)
```typescript
// Generate trains from timetable
const schedule = {
  weekday: generateWeekdayTrains(),
  weekend: generateWeekendTrains(),
  special: generateSpecialEventTrains()
};
```

### Phase 2: Simulated Real-Time
```typescript
// Simulate train movements based on current time
function simulateTrainPositions(trains: Train[]): Train[] {
  const now = new Date();
  
  return trains.map(train => {
    const updatedTrain = { ...train };
    
    // Calculate where train should be
    const position = calculateExpectedPosition(train, now);
    
    // Add random delays (0% chance)
    if (Math.random() < 0.0) {
      updatedTrain.status.delayMinutes = Math.floor(Math.random() * 0);
    }
    
    // Update current location
    updatedTrain.currentLocation = position;
    
    // Update stop statuses
    updatedTrain.stops = updateStopStatuses(train.stops, now);
    
    return updatedTrain;
  });
}
```

## Implementation Plan

### Step 1: Create New Data Types
- [ ] Define enhanced Train interface
- [ ] Define TrainStop interface
- [ ] Define query result interfaces
- [ ] Add real-time status types

### Step 2: Create Train Service
```typescript
// services/trainService.ts
class TrainService {
  // Core queries
  getActiveTrains(): Train[]
  getTrainById(id: string): Train
  getTrainsByStation(stationCode: string): Train[]
  
  // Station queries
  getDepartures(stationCode: string): Departure[]
  getArrivals(stationCode: string): Arrival[]
  
  // Real-time simulation
  updateTrainPositions(): void
  simulateDelay(trainId: string, minutes: number): void
  
  // Journey planning
  findJourneys(from: string, to: string, time: Date): Journey[]
}
```

### Step 3: Update Mock Data
- [ ] Convert existing timetables to train objects
- [ ] Add more realistic service patterns
- [ ] Include special services (heritage steam days)
- [ ] Add maintenance/engineering trains

### Step 4: Create View Components
```typescript
// components/TrainTracker/
├── ActiveTrainsList.tsx      // List of running trains
├── TrainJourneyView.tsx      // Single train detail
├── TrainMap.tsx              // Visual position tracker
└── TrainStatusBadge.tsx      // Status indicator

// components/StationBoard/
├── DepartureBoard.tsx        // Next departures
├── ArrivalBoard.tsx          // Next arrivals
├── PlatformView.tsx          // Platform-specific view
└── StationInfo.tsx           // Facilities & info
```

### Step 5: Add Real-Time Features
- [ ] WebSocket connection simulation
- [ ] Automatic position updates (every 30s)
- [ ] Push notifications for delays
- [ ] Live journey tracking

## Firebase/Firestore Structure

```
firestore/
├── trains/
│   └── {trainId}/
│       ├── schedule (static data)
│       ├── status (real-time updates)
│       └── history (journey logs)
│
├── stations/
│   └── {stationCode}/
│       ├── info (static data)
│       ├── departures (cached, regenerated)
│       └── announcements
│
├── schedules/
│   └── {date}/
│       └── trains[] (daily train list)
│
└── realtime/
    └── positions/
        └── {trainId} (current position)
```

## Benefits of Train-Centric Approach

1. **Scalability**: Easy to add more trains without restructuring
2. **Real-time Ready**: Single source of truth for train status
3. **User Experience**: Natural for journey tracking
4. **Admin Interface**: Edit complete train journey at once
5. **Analytics**: Track performance by train, not just station
6. **Integration**: Ready for real-time GPS/tracking systems

## Migration Path

1. **Keep existing structure** temporarily
2. **Add train-centric layer** on top
3. **Gradually migrate features** to use new model
4. **Remove station-centric code** once complete

## Example Queries

### "Show me the 10:15 from Bishops Lydeard"
```typescript
const train = trains.find(t => 
  t.origin === 'BL' && 
  t.stops[0].scheduledDeparture === '10:15'
);
```

### "What trains stop at Williton in the next hour?"
```typescript
const upcoming = trains.filter(t =>
  t.stops.some(s => 
    s.stationCode === 'WIL' &&
    s.scheduledDeparture > now &&
    s.scheduledDeparture < oneHourLater
  )
);
```

### "Is the 2A15 running on time?"
```typescript
const train = getTrainById('2A15');
const isOnTime = train.status.delayMinutes === 0;
```

## Next Steps

1. **Review and approve** this plan
2. **Create new type definitions**
3. **Build train service layer**
4. **Update mock data generator**
5. **Refactor components** to use new model
6. **Add real-time simulation**
7. **Prepare for Firebase integration**

---

*This restructuring will make the app more maintainable, scalable, and ready for real-world train tracking integration.*