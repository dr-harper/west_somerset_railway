import type { Train, ServiceType } from '../types/train';
import { STATIONS } from '../types/station';

interface TimetableEntry {
  time: string;
  serviceType: ServiceType;
}

const northboundTimetable: Record<string, TimetableEntry[]> = {
  'BL': [
    { time: '10:15', serviceType: 'Diesel' },
    { time: '10:55', serviceType: 'DMU' },
    { time: '12:25', serviceType: 'Diesel' },
    { time: '14:25', serviceType: 'Diesel' },
    { time: '16:40', serviceType: 'Diesel' }
  ],
  'CH': [
    { time: '10:28', serviceType: 'Diesel' },
    { time: '11:07', serviceType: 'DMU' },
    { time: '12:38', serviceType: 'Diesel' },
    { time: '14:38', serviceType: 'Diesel' },
    { time: '16:53', serviceType: 'Diesel' }
  ],
  'STO': [
    { time: '10:38', serviceType: 'Diesel' },
    { time: '11:25', serviceType: 'DMU' },
    { time: '12:48', serviceType: 'Diesel' },
    { time: '14:48', serviceType: 'Diesel' },
    { time: '17:03', serviceType: 'Diesel' }
  ],
  'WIL': [
    { time: '10:48', serviceType: 'Diesel' },
    { time: '11:34', serviceType: 'DMU' },
    { time: '12:58', serviceType: 'Diesel' },
    { time: '14:58', serviceType: 'Diesel' },
    { time: '17:13', serviceType: 'Diesel' }
  ],
  'DON': [
    { time: '10:54', serviceType: 'Diesel' },
    { time: '11:38', serviceType: 'DMU' },
    { time: '13:12', serviceType: 'Diesel' },
    { time: '15:12', serviceType: 'Diesel' },
    { time: '17:27', serviceType: 'Diesel' }
  ],
  'WAT': [
    { time: '11:00', serviceType: 'Diesel' },
    { time: '11:43', serviceType: 'DMU' },
    { time: '13:18', serviceType: 'Diesel' },
    { time: '15:18', serviceType: 'Diesel' },
    { time: '17:33', serviceType: 'Diesel' }
  ],
  'WAS': [
    { time: '11:08', serviceType: 'Diesel' },
    { time: '11:51', serviceType: 'DMU' },
    { time: '13:26', serviceType: 'Diesel' },
    { time: '15:26', serviceType: 'Diesel' },
    { time: '17:41', serviceType: 'Diesel' }
  ],
  'BA': [
    { time: '11:18', serviceType: 'Diesel' },
    { time: '12:00', serviceType: 'DMU' },
    { time: '13:35', serviceType: 'Diesel' },
    { time: '15:35', serviceType: 'Diesel' },
    { time: '17:50', serviceType: 'Diesel' }
  ],
  'DUN': [
    { time: '11:26', serviceType: 'Diesel' },
    { time: '12:07', serviceType: 'DMU' },
    { time: '13:43', serviceType: 'Diesel' },
    { time: '15:43', serviceType: 'Diesel' },
    { time: '17:57', serviceType: 'Diesel' }
  ],
  'MIN': [
    { time: '11:35', serviceType: 'Diesel' },
    { time: '12:14', serviceType: 'DMU' },
    { time: '13:50', serviceType: 'Diesel' },
    { time: '15:50', serviceType: 'Diesel' },
    { time: '18:05', serviceType: 'Diesel' }
  ]
};

const southboundTimetable: Record<string, TimetableEntry[]> = {
  'MIN': [
    { time: '10:00', serviceType: 'Diesel' },
    { time: '12:20', serviceType: 'Diesel' },
    { time: '14:20', serviceType: 'Diesel' },
    { time: '15:15', serviceType: 'DMU' },
    { time: '16:35', serviceType: 'Diesel' }
  ],
  'DUN': [
    { time: '10:08', serviceType: 'Diesel' },
    { time: '12:28', serviceType: 'Diesel' },
    { time: '14:28', serviceType: 'Diesel' },
    { time: '15:23', serviceType: 'DMU' },
    { time: '16:43', serviceType: 'Diesel' }
  ],
  'BA': [
    { time: '10:17', serviceType: 'Diesel' },
    { time: '12:37', serviceType: 'Diesel' },
    { time: '14:37', serviceType: 'Diesel' },
    { time: '15:38', serviceType: 'DMU' },
    { time: '16:52', serviceType: 'Diesel' }
  ],
  'WAS': [
    { time: '10:25', serviceType: 'Diesel' },
    { time: '12:45', serviceType: 'Diesel' },
    { time: '14:45', serviceType: 'Diesel' },
    { time: '15:46', serviceType: 'DMU' },
    { time: '17:00', serviceType: 'Diesel' }
  ],
  'WAT': [
    { time: '10:35', serviceType: 'Diesel' },
    { time: '12:55', serviceType: 'Diesel' },
    { time: '14:55', serviceType: 'Diesel' },
    { time: '15:55', serviceType: 'DMU' },
    { time: '17:10', serviceType: 'Diesel' }
  ],
  'DON': [
    { time: '10:39', serviceType: 'Diesel' },
    { time: '12:59', serviceType: 'Diesel' },
    { time: '14:59', serviceType: 'Diesel' },
    { time: '15:59', serviceType: 'DMU' },
    { time: '17:14', serviceType: 'Diesel' }
  ],
  'WIL': [
    { time: '10:43', serviceType: 'Diesel' },
    { time: '13:03', serviceType: 'Diesel' },
    { time: '15:03', serviceType: 'Diesel' },
    { time: '16:03', serviceType: 'DMU' },
    { time: '17:18', serviceType: 'Diesel' }
  ],
  'STO': [
    { time: '11:03', serviceType: 'Diesel' },
    { time: '13:16', serviceType: 'Diesel' },
    { time: '15:16', serviceType: 'Diesel' },
    { time: '16:15', serviceType: 'DMU' },
    { time: '17:31', serviceType: 'Diesel' }
  ],
  'CH': [
    { time: '11:12', serviceType: 'Diesel' },
    { time: '13:25', serviceType: 'Diesel' },
    { time: '15:25', serviceType: 'Diesel' },
    { time: '16:23', serviceType: 'DMU' },
    { time: '17:40', serviceType: 'Diesel' }
  ],
  'BL': [
    { time: '11:25', serviceType: 'Diesel' },
    { time: '13:37', serviceType: 'Diesel' },
    { time: '15:37', serviceType: 'Diesel' },
    { time: '16:35', serviceType: 'DMU' },
    { time: '17:52', serviceType: 'Diesel' }
  ]
};

export function generateTrains(): Train[] {
  const trains: Train[] = [];
  let trainId = 1;

  // Generate northbound trains
  const northboundServiceCount = northboundTimetable['BL'].length;
  for (let i = 0; i < northboundServiceCount; i++) {
    const stops = STATIONS.map(station => ({
      station,
      departureTime: northboundTimetable[station.code]?.[i]?.time || '',
      isRequestStop: station.isRequestStop
    })).filter(stop => stop.departureTime);

    if (stops.length > 0) {
      trains.push({
        id: `NB${trainId}`,
        departureTime: stops[0].departureTime,
        arrivalTime: stops[stops.length - 1].departureTime,
        origin: 'Bishops Lydeard',
        destination: 'Minehead',
        serviceType: northboundTimetable['BL'][i].serviceType,
        status: 'On Time',
        stops
      });
      trainId++;
    }
  }

  // Generate southbound trains
  const southboundServiceCount = southboundTimetable['MIN'].length;
  for (let i = 0; i < southboundServiceCount; i++) {
    const stops = [...STATIONS].reverse().map(station => ({
      station,
      departureTime: southboundTimetable[station.code]?.[i]?.time || '',
      isRequestStop: station.isRequestStop
    })).filter(stop => stop.departureTime);

    if (stops.length > 0) {
      trains.push({
        id: `SB${trainId}`,
        departureTime: stops[0].departureTime,
        arrivalTime: stops[stops.length - 1].departureTime,
        origin: 'Minehead',
        destination: 'Bishops Lydeard',
        serviceType: southboundTimetable['MIN'][i].serviceType,
        status: 'On Time',
        stops
      });
      trainId++;
    }
  }

  return trains;
}

export const mockTrains = generateTrains();