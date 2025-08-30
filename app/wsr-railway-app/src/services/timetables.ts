import type { Train, TrainStop, StationCode } from '../types/models';
import { mockStations } from './mockTrainData';
import type { TimetableType } from './calendarConfig';
import { getTimetableType } from './calendarConfig';

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

// Blue Timetable Services (from the Blue Timetable image)
export const blueTimetableTrains: Train[] = [
  // Northbound Services (Bishops Lydeard to Minehead)
  {
    id: 'BLUE_NB_1015',
    serviceId: 'BLUE_1015_BL_MIN_STEAM',
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
  {
    id: 'BLUE_NB_1225',
    serviceId: 'BLUE_1225_BL_MIN_SD',
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
      createStop('WIL', '13:08', '13:08', '1'),
      createStop('DON', '13:12', '13:12', '1'),
      createStop('WAT', '13:18', '13:18', '1'),
      createStop('WAS', '13:26', '13:26', '1'),
      createStop('BA', '13:35', '13:35', '1'),
      createStop('DUN', '13:43', '13:43', '1'),
      createStop('MIN', '13:50', null, '1')
    ]
  },
  {
    id: 'BLUE_NB_1425',
    serviceId: 'BLUE_1425_BL_MIN_STEAM',
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
  {
    id: 'BLUE_NB_1640',
    serviceId: 'BLUE_1640_BL_MIN_SD',
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
  {
    id: 'BLUE_SB_1000',
    serviceId: 'BLUE_1000_MIN_BL_SD',
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
  {
    id: 'BLUE_SB_1220',
    serviceId: 'BLUE_1220_MIN_BL_STEAM',
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
  {
    id: 'BLUE_SB_1420',
    serviceId: 'BLUE_1420_MIN_BL_SD',
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
  {
    id: 'BLUE_SB_1635',
    serviceId: 'BLUE_1635_MIN_BL_STEAM',
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
  }
];

// Red Timetable Services (from the Red Timetable image)
export const redTimetableTrains: Train[] = [
  // Northbound Services
  {
    id: 'RED_NB_1015',
    serviceId: 'RED_1015_BL_MIN_STEAM',
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
      createStop('WIL', '10:48', '10:48', '1'),
      createStop('DON', '10:54', '10:54', '1'),
      createStop('WAT', '11:00', '11:00', '1'),
      createStop('WAS', '11:08', '11:08', '1'),
      createStop('BA', '11:16', '11:16', '1'),
      createStop('DUN', '11:26', '11:26', '1'),
      createStop('MIN', '11:35', null, '1')
    ]
  },
  {
    id: 'RED_NB_1225',
    serviceId: 'RED_1225_BL_MIN_DIESEL',
    scheduledDate: getTodayScheduleDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'Diesel',
    operator: 'West Somerset Railway',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('BL', null, '12:25', '1'),
      createStop('CH', '12:38', '12:38', '1'),
      createStop('STO', '12:48', '12:48', '1'),
      createStop('WIL', '12:58', '12:58', '1'),
      createStop('DON', '13:12', '13:12', '1'),
      createStop('WAT', '13:18', '13:18', '1'),
      createStop('WAS', '13:26', '13:26', '1'),
      createStop('BA', '13:34', '13:34', '1'),
      createStop('DUN', '13:43', '13:43', '1'),
      createStop('MIN', '13:50', null, '1')
    ]
  },
  {
    id: 'RED_NB_1425',
    serviceId: 'RED_1425_BL_MIN_STEAM',
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
      createStop('BA', '15:34', '15:34', '1'),
      createStop('DUN', '15:43', '15:43', '1'),
      createStop('MIN', '15:50', null, '1')
    ]
  },

  // Southbound Services
  {
    id: 'RED_SB_1220',
    serviceId: 'RED_1220_MIN_BL_STEAM',
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
      createStop('BA', '12:35', '12:35', '1'),
      createStop('WAS', '12:45', '12:45', '2'),
      createStop('WAT', '12:55', '12:55', '1'),
      createStop('DON', '12:59', '12:59', '1'),
      createStop('WIL', '13:03', '13:03', '2'),
      createStop('STO', '13:16', '13:16', '1'),
      createStop('CH', '13:25', '13:25', '1'),
      createStop('BL', '13:37', null, '2')
    ]
  },
  {
    id: 'RED_SB_1420',
    serviceId: 'RED_1420_MIN_BL_DIESEL',
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
      createStop('MIN', null, '14:20', '1'),
      createStop('DUN', '14:28', '14:28', '1'),
      createStop('BA', '14:35', '14:35', '2'),
      createStop('WAS', '14:45', '14:45', '1'),
      createStop('WAT', '14:55', '14:55', '1'),
      createStop('DON', '14:59', '14:59', '1'),
      createStop('WIL', '15:03', '15:03', '1'),
      createStop('STO', '15:16', '15:16', '1'),
      createStop('CH', '15:25', '15:25', '1'),
      createStop('BL', '15:37', null, '1')
    ]
  },
  {
    id: 'RED_SB_1635',
    serviceId: 'RED_1635_MIN_BL_STEAM',
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
      createStop('BA', '16:50', '16:50', '1'),
      createStop('WAS', '17:00', '17:00', '2'),
      createStop('WAT', '17:10', '17:10', '1'),
      createStop('DON', '17:14', '17:14', '1'),
      createStop('WIL', '17:18', '17:18', '2'),
      createStop('STO', '17:31', '17:31', '1'),
      createStop('CH', '17:40', '17:40', '1'),
      createStop('BL', '17:52', null, '2')
    ]
  }
];

// Purple/Special Event Timetable (Example - Autumn Steam Gala)
export const purpleTimetableTrains: Train[] = [
  {
    id: 'SPECIAL_1000',
    serviceId: 'SPECIAL_1000_BL_MIN',
    scheduledDate: getTodayScheduleDate(),
    origin: 'BL',
    destination: 'MIN',
    serviceType: 'Steam',
    operator: 'West Somerset Railway',
    notes: 'Special Event Service',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('BL', null, '10:00', '1'),
      createStop('CH', '10:13', '10:13', '1'),
      createStop('STO', '10:23', '10:23', '1'),
      createStop('WIL', '10:33', '10:35', '1'),
      createStop('DON', '10:39', '10:39', '1'),
      createStop('WAT', '10:45', '10:45', '1'),
      createStop('WAS', '10:53', '10:55', '1'),
      createStop('BA', '11:03', '11:05', '1'),
      createStop('DUN', '11:13', '11:13', '1'),
      createStop('MIN', '11:20', null, '1')
    ]
  },
  {
    id: 'SPECIAL_1130',
    serviceId: 'SPECIAL_1130_MIN_BL',
    scheduledDate: getTodayScheduleDate(),
    origin: 'MIN',
    destination: 'BL',
    serviceType: 'Steam',
    operator: 'West Somerset Railway',
    notes: 'Special Event Service',
    status: {
      state: 'Scheduled',
      delayMinutes: 0,
      lastUpdated: new Date()
    },
    stops: [
      createStop('MIN', null, '11:30', '1'),
      createStop('DUN', '11:38', '11:38', '1'),
      createStop('BA', '11:46', '11:48', '1'),
      createStop('WAS', '11:56', '11:58', '1'),
      createStop('WAT', '12:06', '12:06', '1'),
      createStop('DON', '12:10', '12:10', '1'),
      createStop('WIL', '12:14', '12:16', '1'),
      createStop('STO', '12:26', '12:26', '1'),
      createStop('CH', '12:35', '12:35', '1'),
      createStop('BL', '12:48', null, '1')
    ]
  }
];

// Function to get trains for a specific timetable type
export function getTrainsForTimetable(timetableType: TimetableType): Train[] {
  switch (timetableType) {
    case 'blue':
      return blueTimetableTrains;
    case 'red':
      return redTimetableTrains;
    case 'purple':
      return purpleTimetableTrains;
    case 'none':
    default:
      return [];
  }
}

// Helper function to calculate current location for a train
function calculateTrainLocation(train: Train): void {
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
  
  // If we can't determine location, check if train hasn't started yet
  const firstStop = train.stops[0];
  if (firstStop.scheduledDeparture && currentTime < firstStop.scheduledDeparture) {
    train.currentLocation = {
      at: firstStop.stationCode,
      lastUpdated: now
    };
  }
}

// Function to create test train if enabled
function createTestTrain(): Train | null {
  // Check if test train is enabled
  const ENABLE_TEST_TRAIN = true; // Can be toggled for testing
  
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

  const testTrain: Train = {
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
  
  // Calculate initial location for the test train
  calculateTrainLocation(testTrain);
  
  return testTrain;
}

// Function to get all trains for a specific date
export function getTrainsForDate(date: Date): Train[] {
  const timetableType = getTimetableType(date);
  const timetableTrains = getTrainsForTimetable(timetableType);
  
  // Add test train if enabled
  const testTrain = createTestTrain();
  if (testTrain) {
    return [testTrain, ...timetableTrains];
  }
  
  return timetableTrains;
}