// Train-centric data models that mirror Firebase/Firestore structure

export type StationCode = 'MIN' | 'DUN' | 'BA' | 'WAS' | 'WAT' | 'DON' | 'WIL' | 'STO' | 'CH' | 'BL';
export type ServiceType = 'Steam' | 'Diesel' | 'DMU';
export type TrainState = 'Scheduled' | 'Running' | 'Completed' | 'Cancelled' | 'Terminated';
export type StopStatus = 'Scheduled' | 'Arrived' | 'Departed' | 'Skipped' | 'Cancelled';
export type StopType = 'Origin' | 'Stop' | 'Destination';

// Primary Train Entity
export interface Train {
  // Identity
  id: string;                    // "2A15" (headcode format)
  serviceId: string;             // "NB_1015_BL_MIN" (unique service identifier)
  
  // Schedule Information
  scheduledDate: Date;           // Operating date
  origin: StationCode;           // "BL"
  destination: StationCode;      // "MIN"
  
  // Service Details
  serviceType: ServiceType;
  operator?: string;             // "West Somerset Railway"
  notes?: string;                // Special service notes
  
  // Real-time Status
  status: TrainStatus;
  currentLocation?: TrainLocation;
  
  // Journey Details
  stops: TrainStop[];
  
  // Metadata (as if from Firestore)
  createdAt?: Date;
  updatedAt?: Date;
}

export interface TrainStatus {
  state: TrainState;
  delayMinutes: number;         // Overall delay (+ late, - early)
  message?: string;             // "Running 5 minutes late due to..."
  lastUpdated: Date;
}

export interface TrainLocation {
  between?: [StationCode, StationCode];  // ["WIL", "DON"]
  at?: StationCode;                       // "DON"
  latitude?: number;
  longitude?: number;
  speed?: number;                         // mph
  heading?: number;                       // degrees
  lastUpdated: Date;
}

export interface TrainStop {
  stationCode: StationCode;
  stationName: string;
  
  // Times (using ISO string format for Firebase compatibility)
  scheduledArrival?: string;    // "10:54" (null for origin)
  scheduledDeparture?: string;  // "10:55" (null for destination)
  actualArrival?: string;       // Real-time update
  actualDeparture?: string;     // Real-time update
  
  // Stop Details
  platform?: string;            // "1"
  isRequestStop: boolean;
  stopType: StopType;
  
  // Status
  status: StopStatus;
  delayMinutes?: number;        // Minutes late (+) or early (-)
}

// Station Entity
export interface Station {
  code: StationCode;
  name: string;
  
  // Location
  coordinates: {
    lat: number;
    lng: number;
  };
  milepost: number;             // Distance from Bishops Lydeard in miles
  
  // Facilities
  facilities: string[];
  isRequestStop: boolean;
  hasPlatform: boolean;
  platforms?: string[];         // ["1", "2"]
  
  // Additional Info
  address?: string;
  parking?: boolean;
  stepFreeAccess?: boolean;
}

// Departure Board Views (generated from Train data)
export interface DepartureBoard {
  station: StationCode;
  generated: Date;
  departures: Departure[];
  arrivals: Arrival[];
}

export interface Departure {
  trainId: string;              // Reference to train.id
  serviceId: string;            // Reference to train.serviceId
  time: string;                 // "10:54"
  destination: string;          // "Minehead"
  platform?: string;
  status: string;               // "On Time" | "Exp 10:59" | "Delayed"
  serviceType: ServiceType;
  delayMinutes?: number;
  isCancelled: boolean;
}

export interface Arrival {
  trainId: string;
  serviceId: string;
  time: string;
  origin: string;
  platform?: string;
  status: string;
  serviceType: ServiceType;
  delayMinutes?: number;
  isCancelled: boolean;
}

// Journey Planning
export interface Journey {
  segments: JourneySegment[];
  departureTime: string;
  arrivalTime: string;
  duration: number;             // minutes
  changes: number;
}

export interface JourneySegment {
  trainId: string;
  serviceId: string;
  from: StationCode;
  to: StationCode;
  departure: string;
  arrival: string;
  serviceType: ServiceType;
}

// Real-time Events (for Firebase listeners)
export interface TrainUpdate {
  trainId: string;
  timestamp: Date;
  type: 'location' | 'delay' | 'cancellation' | 'platform_change';
  data: any;
}

// Schedule Templates (for generating daily services)
export interface ScheduleTemplate {
  id: string;
  name: string;                 // "Weekday Service"
  validFrom: Date;
  validTo: Date;
  daysOfWeek: number[];         // [1,2,3,4,5] = Mon-Fri
  services: ServiceTemplate[];
}

export interface ServiceTemplate {
  serviceId: string;
  origin: StationCode;
  destination: StationCode;
  serviceType: ServiceType;
  stops: ScheduledStop[];
}

export interface ScheduledStop {
  stationCode: StationCode;
  arrival?: string;             // "HH:mm"
  departure?: string;           // "HH:mm"
  platform?: string;
  isRequestStop: boolean;
}

// Helper Types
export interface TimeRange {
  start: string;                // "HH:mm"
  end: string;                  // "HH:mm"
}

export interface ServiceAlert {
  id: string;
  severity: 'info' | 'warning' | 'severe';
  title: string;
  message: string;
  affectedServices: string[];   // Train IDs
  validFrom: Date;
  validTo: Date;
}