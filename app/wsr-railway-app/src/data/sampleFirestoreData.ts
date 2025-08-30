/**
 * Sample data structured for Firestore collections
 * Replace this with actual Firestore queries when Firebase is connected
 * 
 * Collection structure:
 * - trains/{trainId}
 * - stations/{stationCode}
 * - schedules/{date}/trains/{trainId}
 * - realtime/positions/{trainId}
 */

import type { Train, Station, StationCode } from '../types/models';

// ============================================
// STATIONS COLLECTION
// Firestore path: /stations/{stationCode}
// ============================================

export const FIRESTORE_STATIONS: Record<StationCode, Station> = {
  MIN: {
    code: 'MIN',
    name: 'Minehead',
    coordinates: { lat: 51.2024, lng: -3.4731 },
    milepost: 22.75,
    facilities: ['Parking', 'Toilets', 'Cafe', 'Shop', 'Museum', 'Ticket Office'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: true,
    address: 'The Avenue, Minehead, Somerset TA24 5AY'
  },
  DUN: {
    code: 'DUN',
    name: 'Dunster',
    coordinates: { lat: 51.1842, lng: -3.4436 },
    milepost: 20.25,
    facilities: ['Parking', 'Toilets', 'Waiting Room'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: true,
    stepFreeAccess: false,
    address: 'Station Road, Dunster, Somerset TA24 6SF'
  },
  BA: {
    code: 'BA',
    name: 'Blue Anchor',
    coordinates: { lat: 51.1661, lng: -3.3972 },
    milepost: 17.5,
    facilities: ['Parking', 'Toilets', 'Cafe', 'Beach Access'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: true,
    address: 'Blue Anchor Bay, Somerset TA24 6JT'
  },
  WAS: {
    code: 'WAS',
    name: 'Washford',
    coordinates: { lat: 51.1603, lng: -3.3597 },
    milepost: 15.5,
    facilities: ['Parking', 'Toilets', 'Museum', 'Signal Box'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: false,
    address: 'Station Road, Washford, Somerset TA23 0PP'
  },
  WAT: {
    code: 'WAT',
    name: 'Watchet',
    coordinates: { lat: 51.1817, lng: -3.3303 },
    milepost: 13.25,
    facilities: ['Parking', 'Toilets', 'Harbour Views'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: true,
    stepFreeAccess: true,
    address: 'Harbour Road, Watchet, Somerset TA23 0AQ'
  },
  DON: {
    code: 'DON',
    name: 'Doniford Halt',
    coordinates: { lat: 51.1903, lng: -3.3089 },
    milepost: 11.75,
    facilities: [],
    isRequestStop: true,
    hasPlatform: true,
    platforms: ['1'],
    parking: false,
    stepFreeAccess: false,
    address: 'Doniford, Somerset'
  },
  WIL: {
    code: 'WIL',
    name: 'Williton',
    coordinates: { lat: 51.1636, lng: -3.2889 },
    milepost: 9.25,
    facilities: ['Parking', 'Toilets', 'Cafe', 'Diesel Depot'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: true,
    address: 'Station Road, Williton, Somerset TA4 4RQ'
  },
  STO: {
    code: 'STO',
    name: 'Stogumber',
    coordinates: { lat: 51.1375, lng: -3.2528 },
    milepost: 6.0,
    facilities: ['Parking', 'Country Walks'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: true,
    stepFreeAccess: false,
    address: 'Stogumber, Somerset TA4 3TQ'
  },
  CH: {
    code: 'CH',
    name: 'Crowcombe Heathfield',
    coordinates: { lat: 51.1153, lng: -3.2058 },
    milepost: 3.25,
    facilities: ['Historic Station Building'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: false,
    stepFreeAccess: false,
    address: 'Crowcombe, Somerset TA4 4AW'
  },
  BL: {
    code: 'BL',
    name: 'Bishops Lydeard',
    coordinates: { lat: 51.0547, lng: -3.1903 },
    milepost: 0,
    facilities: ['Parking', 'Toilets', 'Cafe', 'Shop', 'Museum', 'Ticket Office', 'Engine Shed'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: true,
    address: 'Bishops Lydeard, Taunton, Somerset TA4 3RU'
  }
};

// ============================================
// TRAINS COLLECTION (Daily Services)
// Firestore path: /schedules/{date}/trains/{trainId}
// ============================================

function getTodayDate(): Date {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return date;
}

export const FIRESTORE_TRAINS: Record<string, Train> = {
  // Morning Northbound Service
  '2C01': {
    id: '2C01',
    serviceId: 'WKD_1015_NB',
    scheduledDate: getTodayDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    notes: 'Stops at all stations',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      {
        stationCode: 'BL',
        stationName: 'Bishops Lydeard',
        scheduledDeparture: '10:15',
        platform: '2',
        isRequestStop: false,
        stopType: 'Origin',
        status: 'Scheduled'
      },
      {
        stationCode: 'CH',
        stationName: 'Crowcombe Heathfield',
        scheduledArrival: '10:28',
        scheduledDeparture: '10:28',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'STO',
        stationName: 'Stogumber',
        scheduledArrival: '10:38',
        scheduledDeparture: '10:38',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WIL',
        stationName: 'Williton',
        scheduledArrival: '10:48',
        scheduledDeparture: '10:48',
        platform: '2',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'DON',
        stationName: 'Doniford Halt',
        scheduledArrival: '10:54',
        scheduledDeparture: '10:54',
        platform: '1',
        isRequestStop: true,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WAT',
        stationName: 'Watchet',
        scheduledArrival: '11:00',
        scheduledDeparture: '11:00',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WAS',
        stationName: 'Washford',
        scheduledArrival: '11:08',
        scheduledDeparture: '11:08',
        platform: '2',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'BA',
        stationName: 'Blue Anchor',
        scheduledArrival: '11:18',
        scheduledDeparture: '11:18',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'DUN',
        stationName: 'Dunster',
        scheduledArrival: '11:26',
        scheduledDeparture: '11:26',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'MIN',
        stationName: 'Minehead',
        scheduledArrival: '11:35',
        platform: '1',
        isRequestStop: false,
        stopType: 'Destination',
        status: 'Scheduled'
      }
    ],
    createdAt: new Date('2024-01-01'),
    updatedAt: new Date()
  },

  // Afternoon Steam Special
  '2S07': {
    id: '2S07',
    serviceId: 'WKD_1425_NB_STEAM',
    scheduledDate: getTodayDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'Steam',
    operator: 'West Somerset Railway',
    notes: 'Heritage steam service with photo stops',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      message: 'Steam locomotive 7828 "Odney Manor"',
      lastUpdated: new Date()
    },
    stops: [
      {
        stationCode: 'BL',
        stationName: 'Bishops Lydeard',
        scheduledDeparture: '14:25',
        platform: '2',
        isRequestStop: false,
        stopType: 'Origin',
        status: 'Scheduled'
      },
      {
        stationCode: 'CH',
        stationName: 'Crowcombe Heathfield',
        scheduledArrival: '14:38',
        scheduledDeparture: '14:40',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'STO',
        stationName: 'Stogumber',
        scheduledArrival: '14:48',
        scheduledDeparture: '14:50',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WIL',
        stationName: 'Williton',
        scheduledArrival: '14:58',
        scheduledDeparture: '15:00',
        platform: '2',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'DON',
        stationName: 'Doniford Halt',
        scheduledArrival: '15:12',
        scheduledDeparture: '15:12',
        platform: '1',
        isRequestStop: true,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WAT',
        stationName: 'Watchet',
        scheduledArrival: '15:18',
        scheduledDeparture: '15:20',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WAS',
        stationName: 'Washford',
        scheduledArrival: '15:26',
        scheduledDeparture: '15:28',
        platform: '2',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'BA',
        stationName: 'Blue Anchor',
        scheduledArrival: '15:35',
        scheduledDeparture: '15:37',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'DUN',
        stationName: 'Dunster',
        scheduledArrival: '15:43',
        scheduledDeparture: '15:45',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'MIN',
        stationName: 'Minehead',
        scheduledArrival: '15:50',
        platform: '1',
        isRequestStop: false,
        stopType: 'Destination',
        status: 'Scheduled'
      }
    ],
    createdAt: new Date('2024-01-01'),
    updatedAt: new Date()
  },

  // Return Southbound Service
  '2C02': {
    id: '2C02',
    serviceId: 'WKD_1000_SB',
    scheduledDate: getTodayDate(),
    origin: 'MIN',
    destination: 'BL',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    notes: 'First service from Minehead',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      {
        stationCode: 'MIN',
        stationName: 'Minehead',
        scheduledDeparture: '10:00',
        platform: '1',
        isRequestStop: false,
        stopType: 'Origin',
        status: 'Scheduled'
      },
      {
        stationCode: 'DUN',
        stationName: 'Dunster',
        scheduledArrival: '10:08',
        scheduledDeparture: '10:08',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'BA',
        stationName: 'Blue Anchor',
        scheduledArrival: '10:17',
        scheduledDeparture: '10:17',
        platform: '2',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WAS',
        stationName: 'Washford',
        scheduledArrival: '10:25',
        scheduledDeparture: '10:25',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WAT',
        stationName: 'Watchet',
        scheduledArrival: '10:35',
        scheduledDeparture: '10:35',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'DON',
        stationName: 'Doniford Halt',
        scheduledArrival: '10:39',
        scheduledDeparture: '10:39',
        platform: '1',
        isRequestStop: true,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WIL',
        stationName: 'Williton',
        scheduledArrival: '10:43',
        scheduledDeparture: '10:43',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'STO',
        stationName: 'Stogumber',
        scheduledArrival: '11:03',
        scheduledDeparture: '11:03',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'CH',
        stationName: 'Crowcombe Heathfield',
        scheduledArrival: '11:12',
        scheduledDeparture: '11:12',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'BL',
        stationName: 'Bishops Lydeard',
        scheduledArrival: '11:25',
        platform: '1',
        isRequestStop: false,
        stopType: 'Destination',
        status: 'Scheduled'
      }
    ],
    createdAt: new Date('2024-01-01'),
    updatedAt: new Date()
  },

  // Express DMU Service
  '2M03': {
    id: '2M03',
    serviceId: 'WKD_1055_NB_EXPRESS',
    scheduledDate: getTodayDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'DMU',
    operator: 'West Somerset Railway',
    notes: 'Fast service - limited stops',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      {
        stationCode: 'BL',
        stationName: 'Bishops Lydeard',
        scheduledDeparture: '10:55',
        platform: '1',
        isRequestStop: false,
        stopType: 'Origin',
        status: 'Scheduled'
      },
      {
        stationCode: 'WIL',
        stationName: 'Williton',
        scheduledArrival: '11:10',
        scheduledDeparture: '11:11',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'WAS',
        stationName: 'Washford',
        scheduledArrival: '11:20',
        scheduledDeparture: '11:21',
        platform: '1',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'BA',
        stationName: 'Blue Anchor',
        scheduledArrival: '11:30',
        scheduledDeparture: '11:31',
        platform: '2',
        isRequestStop: false,
        stopType: 'Stop',
        status: 'Scheduled'
      },
      {
        stationCode: 'MIN',
        stationName: 'Minehead',
        scheduledArrival: '11:45',
        platform: '2',
        isRequestStop: false,
        stopType: 'Destination',
        status: 'Scheduled'
      }
    ],
    createdAt: new Date('2024-01-01'),
    updatedAt: new Date()
  }
};

// ============================================
// REALTIME POSITIONS COLLECTION
// Firestore path: /realtime/positions/{trainId}
// ============================================

export const FIRESTORE_REALTIME_POSITIONS = {
  '2C01': {
    trainId: '2C01',
    timestamp: new Date(),
    location: {
      between: ['WIL', 'DON'] as [StationCode, StationCode],
      latitude: 51.1770,
      longitude: -3.2989,
      speed: 25,
      heading: 315
    },
    nextStop: 'DON',
    delayMinutes: 0
  },
  '2S07': {
    trainId: '2S07',
    timestamp: new Date(),
    location: {
      at: 'WAS' as StationCode,
      latitude: 51.1603,
      longitude: -3.3597,
      speed: 0,
      heading: 315
    },
    nextStop: 'BA',
    delayMinutes: 0,
    message: 'Taking water at Washford'
  }
};

// ============================================
// HELPER FUNCTIONS FOR FIRESTORE QUERIES
// Replace these with actual Firestore queries
// ============================================

/**
 * Example: Get all trains for today
 * In Firebase: 
 * db.collection('schedules').doc(todayDate).collection('trains').get()
 */
export function getTodaysTrains(): Train[] {
  return Object.values(FIRESTORE_TRAINS);
}

/**
 * Example: Get specific train
 * In Firebase:
 * db.collection('schedules').doc(todayDate).collection('trains').doc(trainId).get()
 */
export function getTrainById(trainId: string): Train | null {
  return FIRESTORE_TRAINS[trainId] || null;
}

/**
 * Example: Get all stations
 * In Firebase:
 * db.collection('stations').get()
 */
export function getAllStations(): Station[] {
  return Object.values(FIRESTORE_STATIONS);
}

/**
 * Example: Get station by code
 * In Firebase:
 * db.collection('stations').doc(stationCode).get()
 */
export function getStationByCode(code: StationCode): Station | null {
  return FIRESTORE_STATIONS[code] || null;
}

/**
 * Example: Subscribe to train position updates
 * In Firebase:
 * db.collection('realtime').doc('positions').doc(trainId)
 *   .onSnapshot((doc) => callback(doc.data()))
 */
export function subscribeToTrainPosition(trainId: string, callback: (position: any) => void) {
  // Simulate real-time updates
  const position = FIRESTORE_REALTIME_POSITIONS[trainId as keyof typeof FIRESTORE_REALTIME_POSITIONS];
  if (position) {
    callback(position);
  }
}

// ============================================
// SCHEDULE TEMPLATES (for recurring services)
// ============================================

export const SCHEDULE_TEMPLATES = {
  weekday: {
    id: 'weekday_standard',
    name: 'Weekday Standard Service',
    validFrom: new Date('2024-01-01'),
    validTo: new Date('2024-12-31'),
    daysOfWeek: [1, 2, 3, 4, 5], // Mon-Fri
    services: ['2C01', '2C02', '2M03', '2S07']
  },
  weekend: {
    id: 'weekend_enhanced',
    name: 'Weekend Enhanced Service',
    validFrom: new Date('2024-01-01'),
    validTo: new Date('2024-12-31'),
    daysOfWeek: [0, 6], // Sat-Sun
    services: ['2C01', '2C02', '2M03', '2S07', '2C05', '2S06']
  },
  special: {
    id: 'special_events',
    name: 'Special Event Days',
    validFrom: new Date('2024-01-01'),
    validTo: new Date('2024-12-31'),
    dates: [
      '2024-12-25', // Christmas
      '2024-12-26', // Boxing Day
      '2024-12-31', // New Year's Eve
    ],
    services: ['2S07', '2S08', '2S09'] // All steam services
  }
};

// ============================================
// SERVICE ALERTS & ANNOUNCEMENTS
// ============================================

export const SERVICE_ALERTS = [
  {
    id: 'alert_001',
    severity: 'info' as const,
    title: 'Steam Service Today',
    message: 'Heritage steam locomotive running on the 14:25 service from Bishops Lydeard',
    affectedServices: ['2S07'],
    validFrom: new Date(),
    validTo: new Date(Date.now() + 86400000)
  },
  {
    id: 'alert_002',
    severity: 'warning' as const,
    title: 'Request Stop Reminder',
    message: 'Doniford Halt is a request stop. Please inform the guard if you wish to alight.',
    affectedServices: [],
    validFrom: new Date(),
    validTo: new Date(Date.now() + 86400000)
  }
];