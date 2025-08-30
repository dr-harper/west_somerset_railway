import type { 
  Train, 
  Station, 
  DepartureBoard, 
  Departure, 
  Arrival,
  StationCode,
  Journey,
  JourneySegment
} from '../types/models';
import { mockTrains, mockStations } from './mockTrainData';

// Firebase-like interface for train service
// When Firebase is added, this will use Firestore instead of mock data
export class TrainService {
  private trains: Map<string, Train> = new Map();
  private stations: Map<StationCode, Station> = new Map();
  private updateInterval: NodeJS.Timeout | null = null;
  private listeners: Map<string, Set<(data: any) => void>> = new Map();

  constructor() {
    // Initialize with mock data (will be replaced with Firestore)
    this.loadMockData();
    
    // Start real-time simulation (will be replaced with Firestore listeners)
    this.startRealTimeSimulation();
  }

  private loadMockData() {
    // Load trains
    mockTrains.forEach(train => {
      this.trains.set(train.id, train);
    });

    // Load stations
    mockStations.forEach(station => {
      this.stations.set(station.code, station);
    });
  }

  // --- Core Train Queries (Firebase-like) ---

  async getTrainById(id: string): Promise<Train | null> {
    // Simulates Firestore get()
    return Promise.resolve(this.trains.get(id) || null);
  }

  async getActiveTrains(): Promise<Train[]> {
    // Simulates Firestore query
    const trains = Array.from(this.trains.values()).filter(train => {
      return train.status.state === 'Running' || train.status.state === 'Scheduled';
    });
    return Promise.resolve(trains);
  }

  async getTrainsByDateRange(start: Date, end: Date): Promise<Train[]> {
    // Simulates Firestore query with date filter
    const trains = Array.from(this.trains.values()).filter(train => {
      return train.scheduledDate >= start && train.scheduledDate <= end;
    });
    return Promise.resolve(trains);
  }

  // --- Station Queries ---

  async getStation(code: StationCode): Promise<Station | null> {
    return Promise.resolve(this.stations.get(code) || null);
  }

  async getAllStations(): Promise<Station[]> {
    return Promise.resolve(Array.from(this.stations.values()));
  }

  async getDepartureBoard(stationCode: StationCode, limit = 10): Promise<DepartureBoard> {
    // For development: show next day's first services if after 8pm
    const now = new Date();
    let currentTime = now.toTimeString().slice(0, 5); // "HH:mm"
    const hour = parseInt(currentTime.split(':')[0]);
    
    // If after 8pm or before 10am, show morning services starting from 10:00
    const showNextDay = hour >= 20 || hour < 10;
    if (showNextDay) {
      currentTime = "09:00"; // Show services from 10:00 onwards
    }
    
    const departures: Departure[] = [];
    const arrivals: Arrival[] = [];

    // Generate departures from train data
    for (const train of this.trains.values()) {
      const stop = train.stops.find(s => s.stationCode === stationCode);
      
      if (stop && stop.scheduledDeparture) {
        // Check if this is a future departure
        if (stop.scheduledDeparture >= currentTime) {
          departures.push({
            trainId: train.id,
            serviceId: train.serviceId,
            time: stop.scheduledDeparture,
            destination: this.stations.get(train.destination)?.name || train.destination,
            platform: stop.platform,
            status: this.formatStatus(stop.delayMinutes),
            serviceType: train.serviceType,
            delayMinutes: stop.delayMinutes,
            isCancelled: stop.status === 'Cancelled'
          });
        }
      }

      if (stop && stop.scheduledArrival) {
        // Check if this is a future arrival
        if (stop.scheduledArrival >= currentTime) {
          arrivals.push({
            trainId: train.id,
            serviceId: train.serviceId,
            time: stop.scheduledArrival,
            origin: this.stations.get(train.origin)?.name || train.origin,
            platform: stop.platform,
            status: this.formatStatus(stop.delayMinutes),
            serviceType: train.serviceType,
            delayMinutes: stop.delayMinutes,
            isCancelled: stop.status === 'Cancelled'
          });
        }
      }
    }

    // Sort by time and limit
    departures.sort((a, b) => a.time.localeCompare(b.time));
    arrivals.sort((a, b) => a.time.localeCompare(b.time));

    return {
      station: stationCode,
      generated: new Date(),
      departures: departures.slice(0, limit),
      arrivals: arrivals.slice(0, limit)
    };
  }

  // --- Journey Planning ---

  async findJourneys(
    from: StationCode, 
    to: StationCode, 
    departAfter?: string
  ): Promise<Journey[]> {
    const journeys: Journey[] = [];
    const currentTime = departAfter || new Date().toTimeString().slice(0, 5);

    // Find direct trains
    for (const train of this.trains.values()) {
      const fromStop = train.stops.find(s => s.stationCode === from);
      const toStop = train.stops.find(s => s.stationCode === to);

      if (fromStop && toStop) {
        const fromIndex = train.stops.indexOf(fromStop);
        const toIndex = train.stops.indexOf(toStop);

        // Check if it's in the right direction and after desired time
        if (fromIndex < toIndex && 
            fromStop.scheduledDeparture && 
            toStop.scheduledArrival &&
            fromStop.scheduledDeparture >= currentTime) {
          
          const segment: JourneySegment = {
            trainId: train.id,
            serviceId: train.serviceId,
            from,
            to,
            departure: fromStop.scheduledDeparture,
            arrival: toStop.scheduledArrival,
            serviceType: train.serviceType
          };

          journeys.push({
            segments: [segment],
            departureTime: fromStop.scheduledDeparture,
            arrivalTime: toStop.scheduledArrival,
            duration: this.calculateDuration(fromStop.scheduledDeparture, toStop.scheduledArrival),
            changes: 0
          });
        }
      }
    }

    // Sort by departure time
    journeys.sort((a, b) => a.departureTime.localeCompare(b.departureTime));

    return Promise.resolve(journeys.slice(0, 5)); // Return top 5 journeys
  }

  // --- Real-time Updates (Firebase-like listeners) ---

  onTrainUpdate(trainId: string, callback: (train: Train) => void): () => void {
    const key = `train:${trainId}`;
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(key)?.delete(callback);
    };
  }

  onDepartureBoardUpdate(stationCode: StationCode, callback: (board: DepartureBoard) => void): () => void {
    const key = `station:${stationCode}`;
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key)!.add(callback);

    // Return unsubscribe function
    return () => {
      this.listeners.get(key)?.delete(callback);
    };
  }

  // --- Real-time Simulation (will be removed when using Firebase) ---

  private startRealTimeSimulation() {
    // Update train positions every 30 seconds
    this.updateInterval = setInterval(() => {
      this.updateTrainPositions();
    }, 30000);
  }

  private updateTrainPositions() {
    const now = new Date();
    const currentTime = now.toTimeString().slice(0, 5);

    for (const train of this.trains.values()) {
      // Update train status based on current time
      const firstStop = train.stops[0];
      const lastStop = train.stops[train.stops.length - 1];

      if (firstStop.scheduledDeparture && lastStop.scheduledArrival) {
        if (currentTime < firstStop.scheduledDeparture) {
          train.status.state = 'Scheduled';
        } else if (currentTime > lastStop.scheduledArrival) {
          train.status.state = 'Completed';
        } else {
          train.status.state = 'Running';
          
          // Find current position
          for (let i = 0; i < train.stops.length - 1; i++) {
            const currentStop = train.stops[i];
            const nextStop = train.stops[i + 1];
            
            if (currentStop.scheduledDeparture && 
                nextStop.scheduledArrival &&
                currentTime >= currentStop.scheduledDeparture && 
                currentTime < nextStop.scheduledArrival) {
              train.currentLocation = {
                between: [currentStop.stationCode, nextStop.stationCode],
                lastUpdated: now
              };
              break;
            }
          }
        }

        // Simulate random delays (5% chance)
        if (Math.random() < 0.05 && train.status.state === 'Running') {
          const delayMinutes = Math.floor(Math.random() * 10) + 1;
          train.status.delayMinutes = delayMinutes;
          train.status.message = `Running ${delayMinutes} minutes late`;
        }
      }

      // Notify listeners
      this.notifyListeners(`train:${train.id}`, train);
    }

    // Update station departure boards
    for (const stationCode of this.stations.keys()) {
      this.getDepartureBoard(stationCode).then(board => {
        this.notifyListeners(`station:${stationCode}`, board);
      });
    }
  }

  private notifyListeners(key: string, data: any) {
    const listeners = this.listeners.get(key);
    if (listeners) {
      listeners.forEach(callback => callback(data));
    }
  }

  // --- Helper Methods ---

  private formatStatus(delayMinutes?: number): string {
    if (!delayMinutes || delayMinutes === 0) {
      return 'On Time';
    } else if (delayMinutes > 0) {
      return `Exp ${delayMinutes} min late`;
    } else {
      return `Running early`;
    }
  }

  private calculateDuration(start: string, end: string): number {
    const [startHour, startMin] = start.split(':').map(Number);
    const [endHour, endMin] = end.split(':').map(Number);
    
    const startMinutes = startHour * 60 + startMin;
    const endMinutes = endHour * 60 + endMin;
    
    return endMinutes - startMinutes;
  }

  // Cleanup
  dispose() {
    if (this.updateInterval) {
      clearInterval(this.updateInterval);
    }
    this.listeners.clear();
  }
}

// Singleton instance
export const trainService = new TrainService();