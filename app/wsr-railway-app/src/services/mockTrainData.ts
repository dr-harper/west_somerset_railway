import type { Train, Station, StationCode, TrainStop } from '../types/models';

// Configuration flag to enable/disable test train
// Set to true to show a train that's always running for testing
// Set to false to only show real scheduled trains
const ENABLE_TEST_TRAIN = true;

// Station data with coordinates and facilities
export const mockStations: Station[] = [
  {
    code: 'MIN',
    name: 'Minehead',
    coordinates: { lat: 51.206815, lng: -3.4711559 },
    milepost: 22.75,
    facilities: ['Parking', 'Toilets', 'Cafe', 'Shop', 'Museum'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: true
  },
  {
    code: 'DUN',
    name: 'Dunster',
    coordinates: { lat: 51.1931315884899, lng: -3.4385530693148945 },
    milepost: 20.25,
    facilities: ['Parking', 'Toilets'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: true,
    stepFreeAccess: false
  },
  {
    code: 'BA',
    name: 'Blue Anchor',
    coordinates: { lat: 51.18177271081976, lng: -3.4012355263416287 },
    milepost: 17.5,
    facilities: ['Parking', 'Toilets', 'Cafe'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: true
  },
  {
    code: 'WAS',
    name: 'Washford',
    coordinates: { lat: 51.16169572799292, lng: -3.368545896756289 },
    milepost: 15.5,
    facilities: ['Parking', 'Toilets', 'Museum'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: true,
    stepFreeAccess: false
  },
  {
    code: 'WAT',
    name: 'Watchet',
    coordinates: { lat: 51.18083509803016, lng: -3.329631778829393 },
    milepost: 13.25,
    facilities: ['Parking', 'Toilets'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: true,
    stepFreeAccess: true
  },
  {
    code: 'DON',
    name: 'Doniford Halt',
    coordinates: { lat: 51.17841737732154, lng: -3.3113258133497485 },
    milepost: 11.75,
    facilities: [],
    isRequestStop: true,
    hasPlatform: true,
    platforms: ['1'],
    parking: false,
    stepFreeAccess: false
  },
  {
    code: 'WIL',
    name: 'Williton',
    coordinates: { lat: 51.166215218812056, lng: -3.309489866648678 },
    milepost: 9.25,
    facilities: ['Parking', 'Toilets', 'Cafe'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: true
  },
  {
    code: 'STO',
    name: 'Stogumber',
    coordinates: { lat: 51.12791469181247, lng: -3.2733470229230224 },
    milepost: 6.0,
    facilities: ['Parking'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: true,
    stepFreeAccess: false
  },
  {
    code: 'CH',
    name: 'Crowcombe Heathfield',
    coordinates: { lat: 51.102683806851786, lng: -3.2338928074524973 },
    milepost: 3.25,
    facilities: [],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1'],
    parking: false,
    stepFreeAccess: false
  },
  {
    code: 'BL',
    name: 'Bishops Lydeard',
    coordinates: { lat: 51.05526555357071, lng: -3.1939831447400424 },
    milepost: 0,
    facilities: ['Parking', 'Toilets', 'Cafe', 'Shop', 'Museum'],
    isRequestStop: false,
    hasPlatform: true,
    platforms: ['1', '2'],
    parking: true,
    stepFreeAccess: true
  }
];

// Helper function to create train stops
function createStop(
  stationCode: StationCode,
  arrival: string | null,
  departure: string | null,
  platform: string = '1'
): TrainStop {
  const station = mockStations.find(s => s.code === stationCode)!;

  return {
    stationCode,
    stationName: station.name,
    scheduledArrival: arrival || undefined,
    scheduledDeparture: departure || undefined,
    actualArrival: undefined,
    actualDeparture: undefined,
    platform,
    isRequestStop: station.isRequestStop,
    stopType: !arrival ? 'Origin' : !departure ? 'Destination' : 'Stop',
    status: 'Scheduled',
    delayMinutes: 0
  };
}

// Generate today's date at midnight
function getTodayScheduleDate(): Date {
  const date = new Date();
  date.setHours(0, 0, 0, 0);
  return date;
}

// Helper to adjust times for test train (30 minutes ago)
function adjustTimeForTestTrain(timeStr: string | null): string | null {
  if (!timeStr) return null;

  const now = new Date();
  const [hours, minutes] = timeStr.split(':').map(Number);

  // Create a date object for today with the given time
  const scheduleTime = new Date();
  scheduleTime.setHours(hours, minutes, 0, 0);

  // Subtract 30 minutes to make it start 30 minutes ago
  scheduleTime.setMinutes(scheduleTime.getMinutes() - 30);

  // Return in HH:MM format
  return scheduleTime.toTimeString().slice(0, 5);
}

// Function to create test train if enabled
function createTestTrain(): Train | null {
  if (!ENABLE_TEST_TRAIN) return null;

  const now = new Date();
  const thirtyMinsAgo = new Date(now.getTime() - 30 * 60000);
  const baseTime = thirtyMinsAgo.toTimeString().slice(0, 5);
  const [baseHour, baseMin] = baseTime.split(':').map(Number);

  // Create a train schedule starting 30 minutes ago
  const addMinutes = (minutes: number) => {
    const time = new Date();
    time.setHours(baseHour, baseMin + minutes, 0, 0);
    return time.toTimeString().slice(0, 5);
  };

  return {
    id: 'TEST01',
    serviceId: 'TEST_TRAIN_JOURNEY',
    scheduledDate: getTodayScheduleDate(),
    origin: 'MIN',
    destination: 'BL',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    notes: 'Test train for demonstration',
    status: {
      state: 'Running',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('MIN', null, addMinutes(0), '1'),
      createStop('DUN', addMinutes(8), addMinutes(9), '1'),
      createStop('BA', addMinutes(17), addMinutes(18), '1'),
      createStop('WAS', addMinutes(25), addMinutes(26), '1'),
      createStop('WAT', addMinutes(35), addMinutes(36), '1'),
      createStop('DON', addMinutes(39), addMinutes(40), '1'),
      createStop('WIL', addMinutes(43), addMinutes(44), '1'),
      createStop('STO', addMinutes(53), addMinutes(54), '1'),
      createStop('CH', addMinutes(62), addMinutes(63), '1'),
      createStop('BL', addMinutes(75), null, '1')
    ]
  };
}

// Create mock trains based on real WSR timetable from the image
const baseTrains: Train[] = [
  // Northbound Services (Bishops Lydeard to Minehead)
  // First Steam Service
  {
    id: '1S01',
    serviceId: 'NB_1015_BL_MIN_STEAM',
    scheduledDate: getTodayScheduleDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'Steam',
    operator: 'West Somerset Railway',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('BL', null, '10:15', '1'),
      createStop('CH', '10:28', '10:28', '1'),
      createStop('STO', '10:38', '10:38', '1'),
      createStop('WIL', '10:50', '10:50', '1'),
      createStop('DON', '10:54', '10:54', '1'),
      createStop('WAT', '11:00', '11:00', '1'),
      createStop('WAS', '11:08', '11:08', '1'),
      createStop('BA', '11:18', '11:18', '1'),
      createStop('DUN', '11:26', '11:26', '1'),
      createStop('MIN', '11:35', null, '1')
    ]
  },
  // Second Service (S/D - Steam or Diesel)
  {
    id: '2D02',
    serviceId: 'NB_1225_BL_MIN_SD',
    scheduledDate: getTodayScheduleDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    notes: 'Steam or Diesel service',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('BL', null, '12:25', '1'),
      createStop('CH', '12:38', '12:38', '1'),
      createStop('STO', '12:48', '12:48', '1'),
      createStop('WIL', '13:00', '13:00', '1'),
      createStop('DON', '13:12', '13:12', '1'),
      createStop('WAT', '13:18', '13:18', '1'),
      createStop('WAS', '13:26', '13:26', '1'),
      createStop('BA', '13:35', '13:35', '1'),
      createStop('DUN', '13:43', '13:43', '1'),
      createStop('MIN', '13:50', null, '1')
    ]
  },
  // Third Steam Service
  {
    id: '3S03',
    serviceId: 'NB_1425_BL_MIN_STEAM',
    scheduledDate: getTodayScheduleDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'Steam',
    operator: 'West Somerset Railway',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('BL', null, '14:25', '2'),
      createStop('CH', '14:38', '14:38', '1'),
      createStop('STO', '14:48', '14:48', '1'),
      createStop('WIL', '14:58', '14:58', '2'),
      createStop('DON', '15:12', '15:12', '1'),
      createStop('WAT', '15:18', '15:18', '1'),
      createStop('WAS', '15:26', '15:26', '2'),
      createStop('BA', '15:35', '15:35', '1'),
      createStop('DUN', '15:43', '15:43', '1'),
      createStop('MIN', '15:50', null, '1')
    ]
  },
  // Fourth Service (S/D)
  {
    id: '4D04',
    serviceId: 'NB_1640_BL_MIN_SD',
    scheduledDate: getTodayScheduleDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    notes: 'Steam or Diesel service',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('BL', null, '16:40', '1'),
      createStop('CH', '16:53', '16:53', '1'),
      createStop('STO', '17:03', '17:03', '1'),
      createStop('WIL', '17:23', '17:23', '1'),
      createStop('DON', '17:27', '17:27', '1'),
      createStop('WAT', '17:33', '17:33', '1'),
      createStop('WAS', '17:41', '17:41', '1'),
      createStop('BA', '17:50', '17:50', '1'),
      createStop('DUN', '17:57', '17:57', '1'),
      createStop('MIN', '18:05', null, '1')
    ]
  },

  // Southbound Services (Minehead to Bishops Lydeard)
  // First Southbound (S/D)
  {
    id: '1D05',
    serviceId: 'SB_1000_MIN_BL_SD',
    scheduledDate: getTodayScheduleDate(),
    origin: 'MIN',
    destination: 'BL',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    notes: 'Steam or Diesel service',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('MIN', null, '10:00', '1'),
      createStop('DUN', '10:08', '10:08', '1'),
      createStop('BA', '10:17', '10:17', '2'),
      createStop('WAS', '10:25', '10:25', '1'),
      createStop('WAT', '10:35', '10:35', '1'),
      createStop('DON', '10:39', '10:39', '1'),
      createStop('WIL', '10:43', '10:43', '1'),
      createStop('STO', '11:03', '11:03', '1'),
      createStop('CH', '11:12', '11:12', '1'),
      createStop('BL', '11:25', null, '1')
    ]
  },
  // Second Southbound Steam
  {
    id: '2S06',
    serviceId: 'SB_1220_MIN_BL_STEAM',
    scheduledDate: getTodayScheduleDate(),
    origin: 'MIN',
    destination: 'BL',
    serviceType: 'Steam',
    operator: 'West Somerset Railway',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('MIN', null, '12:20', '2'),
      createStop('DUN', '12:28', '12:28', '1'),
      createStop('BA', '12:37', '12:37', '1'),
      createStop('WAS', '12:45', '12:45', '2'),
      createStop('WAT', '12:55', '12:55', '1'),
      createStop('DON', '12:59', '12:59', '1'),
      createStop('WIL', '13:03', '13:03', '2'),
      createStop('STO', '13:16', '13:16', '1'),
      createStop('CH', '13:25', '13:25', '1'),
      createStop('BL', '13:37', null, '2')
    ]
  },
  // Third Southbound (S/D)
  {
    id: '3D07',
    serviceId: 'SB_1420_MIN_BL_SD',
    scheduledDate: getTodayScheduleDate(),
    origin: 'MIN',
    destination: 'BL',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    notes: 'Steam or Diesel service',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('MIN', null, '14:20', '1'),
      createStop('DUN', '14:28', '14:28', '1'),
      createStop('BA', '14:37', '14:37', '2'),
      createStop('WAS', '14:45', '14:45', '1'),
      createStop('WAT', '14:55', '14:55', '1'),
      createStop('DON', '14:59', '14:59', '1'),
      createStop('WIL', '15:03', '15:03', '1'),
      createStop('STO', '15:16', '15:16', '1'),
      createStop('CH', '15:25', '15:25', '1'),
      createStop('BL', '15:37', null, '1')
    ]
  },
  // Fourth Southbound Steam
  {
    id: '4S08',
    serviceId: 'SB_1635_MIN_BL_STEAM',
    scheduledDate: getTodayScheduleDate(),
    origin: 'MIN',
    destination: 'BL',
    serviceType: 'Steam',
    operator: 'West Somerset Railway',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('MIN', null, '16:35', '2'),
      createStop('DUN', '16:43', '16:43', '1'),
      createStop('BA', '16:52', '16:52', '1'),
      createStop('WAS', '17:00', '17:00', '2'),
      createStop('WAT', '17:10', '17:10', '1'),
      createStop('DON', '17:14', '17:14', '1'),
      createStop('WIL', '17:18', '17:18', '2'),
      createStop('STO', '17:31', '17:31', '1'),
      createStop('CH', '17:40', '17:40', '1'),
      createStop('BL', '17:52', null, '2')
    ]
  },
  {
    id: '2C10',
    serviceId: 'SB_1635_MIN_BL',
    scheduledDate: getTodayScheduleDate(),
    origin: 'MIN',
    destination: 'BL',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('MIN', null, '16:35', '1'),
      createStop('DUN', '16:43', '16:43', '1'),
      createStop('BA', '16:52', '16:52', '2'),
      createStop('WAS', '17:00', '17:00', '1'),
      createStop('WAT', '17:10', '17:10', '1'),
      createStop('DON', '17:14', '17:14', '1'),
      createStop('WIL', '17:18', '17:18', '1'),
      createStop('STO', '17:31', '17:31', '1'),
      createStop('CH', '17:40', '17:40', '1'),
      createStop('BL', '17:52', null, '1')
    ]
  }
];

// Export the mock trains array, including test train if enabled
export const mockTrains: Train[] = [
  ...(createTestTrain() ? [createTestTrain()!] : []),
  ...baseTrains
];

// Simulate some trains as currently running based on time
export function updateTrainStatuses() {
  const now = new Date();
  const currentTime = now.toTimeString().slice(0, 5); // "HH:mm"

  // Update all trains based on their actual schedule times
  mockTrains.forEach(train => {
    const firstDeparture = train.stops[0].scheduledDeparture;
    const lastArrival = train.stops[train.stops.length - 1].scheduledArrival;

    if (firstDeparture && lastArrival) {
      // Check if train should be running
      if (currentTime >= firstDeparture && currentTime <= lastArrival) {
        train.status.state = 'Running';

        // Find current position
        for (let i = 0; i < train.stops.length; i++) {
          const stop = train.stops[i];

          // Check if at station
          if (stop.scheduledArrival && stop.scheduledDeparture) {
            if (currentTime >= stop.scheduledArrival && currentTime < stop.scheduledDeparture) {
              train.currentLocation = {
                at: stop.stationCode,
                lastUpdated: now
              };
              stop.status = 'Arrived';
              break;
            }
          }

          // Check if between stations
          if (i < train.stops.length - 1) {
            const nextStop = train.stops[i + 1];
            const thisDeparture = stop.scheduledDeparture;
            const nextArrival = nextStop.scheduledArrival;

            if (thisDeparture && nextArrival &&
              currentTime >= thisDeparture && currentTime < nextArrival) {
              train.currentLocation = {
                between: [stop.stationCode, nextStop.stationCode],
                lastUpdated: now
              };
              stop.status = 'Departed';
              break;
            }
          }

          // Mark passed stops
          if (stop.scheduledDeparture && currentTime > stop.scheduledDeparture) {
            stop.status = 'Departed';
          }
        }
      } else if (currentTime > lastArrival) {
        train.status.state = 'Completed';
        train.stops.forEach(stop => stop.status = 'Departed');
      }
    }
  });
}

// Initialize train statuses
updateTrainStatuses();