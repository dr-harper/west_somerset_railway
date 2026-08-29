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
import { buildTestTrain, mockStations } from './mockTrainData';
import { getSetting } from './settings';
import { getDayInfo, getSpecialEvent, timetableColors, timetableNames, timetableSummaries } from './calendarConfig';
import { getTrainsForDate } from './timetables';
import type { DayKind, TimetableType } from './calendarConfig';

// Firebase-like interface for train service
// When Firebase is added, this will use Firestore instead of mock data
export class TrainService {
  private trains: Map<string, Train> = new Map();
  private stations: Map<StationCode, Station> = new Map();
  private updateInterval: ReturnType<typeof setInterval> | null = null;
  private listeners: Map<string, Set<(data: unknown) => void>> = new Map();
  private currentDate: Date = new Date();

  constructor() {
    // Initialize with mock data (will be replaced with Firestore)
    this.loadMockData();

    // Immediately update train positions and status
    this.updateTrainPositions();

    // Start real-time simulation (will be replaced with Firestore listeners)
    this.startRealTimeSimulation();
  }

  private loadMockData() {
    // Load trains based on calendar
    const todayTrains = getTrainsForDate(this.currentDate);
    todayTrains.forEach(train => {
      // Calculate initial location for each train
      this.calculateCurrentLocation(train);
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
    // Built fresh on each call rather than loaded once, so switching the
    // setting takes effect on the next poll instead of needing a reload —
    // and so its times stay relative to now rather than to page load.
    if (getSetting('testTrain')) {
      const test = buildTestTrain();
      this.calculateCurrentLocation(test);
      trains.push(test);
    }
    return Promise.resolve(trains);
  }

  // Get current timetable information
  async getTimetableInfo(): Promise<{ type: TimetableType; kind: DayKind; name: string; color: string; summary: string; specialEvent?: string }> {
    const info = getDayInfo(this.currentDate);
    const type = info.kind === 'service' || info.kind === 'event' ? info.family : 'none';
    return Promise.resolve({
      type,
      kind: info.kind,
      name: info.patternTitle ?? timetableNames[type],
      color: timetableColors[type],
      summary: timetableSummaries[type],
      specialEvent: getSpecialEvent(this.currentDate)
    });
  }

  // Set the date for the service (useful for testing different days)
  setServiceDate(date: Date): void {
    this.currentDate = date;
    this.trains.clear();
    this.loadMockData();
    // Immediately update positions after loading new data
    this.updateTrainPositions();
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
    this.listeners.get(key)!.add(callback as (data: unknown) => void);

    // Return unsubscribe function
    return () => {
      this.listeners.get(key)?.delete(callback as (data: unknown) => void);
    };
  }

  onDepartureBoardUpdate(stationCode: StationCode, callback: (board: DepartureBoard) => void): () => void {
    const key = `station:${stationCode}`;
    if (!this.listeners.has(key)) {
      this.listeners.set(key, new Set());
    }
    this.listeners.get(key)!.add(callback as (data: unknown) => void);

    // Return unsubscribe function
    return () => {
      this.listeners.get(key)?.delete(callback as (data: unknown) => void);
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
          // Use the centralized location calculation function
          this.calculateCurrentLocation(train);
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

  private notifyListeners(key: string, data: unknown) {
    const listeners = this.listeners.get(key);
    if (listeners) {
      listeners.forEach(callback => callback(data));
    }
  }

  // --- Helper Methods ---

  private calculateCurrentLocation(train: Train): void {
    const now = new Date();
    const currentTime = now.toTimeString().slice(0, 5);

    // Find current position based on schedule
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
        return;
      }
    }

    // Check if train is at a station
    for (const stop of train.stops) {
      if (stop.scheduledArrival && stop.scheduledDeparture &&
        currentTime >= stop.scheduledArrival &&
        currentTime < stop.scheduledDeparture) {
        train.currentLocation = {
          at: stop.stationCode,
          lastUpdated: now
        };
        return;
      }
    }

    // If we can't determine location, set to origin
    if (train.stops.length > 0) {
      train.currentLocation = {
        at: train.stops[0].stationCode,
        lastUpdated: now
      };
    }
  }

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