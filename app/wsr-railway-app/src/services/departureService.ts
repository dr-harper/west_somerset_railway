import type { Departure } from '../types/train';
import type { Station } from '../types/station';
import { mockTrains } from './mockData';

export function getDeparturesForStation(
  station: Station,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  _date: Date
): Departure[] {
  const departures: Departure[] = [];

  mockTrains.forEach(train => {
    const stopAtStation = train.stops.find(stop => stop.station.id === station.id);
    
    if (stopAtStation && stopAtStation.departureTime) {
      // Determine destination based on direction
      let destination = '';
      const stationIndex = train.stops.findIndex(s => s.station.id === station.id);
      
      if (stationIndex < train.stops.length - 1) {
        // Not the last stop, so show the final destination
        destination = train.stops[train.stops.length - 1].station.name;
      } else {
        // This is the last stop, no departures from here for this service
        return;
      }

      departures.push({
        train,
        station,
        scheduledTime: stopAtStation.departureTime,
        expectedTime: stopAtStation.departureTime,
        destination,
        serviceType: train.serviceType,
        status: train.status,
        platform: train.platform
      });
    }
  });

  return departures.sort((a, b) => 
    a.scheduledTime.localeCompare(b.scheduledTime)
  );
}

export function getNextDepartures(
  station: Station,
  date: Date,
  count: number = 10
): Departure[] {
  const allDepartures = getDeparturesForStation(station, date);
  const currentTime = new Date().toTimeString().slice(0, 5);
  
  // For today, filter to show only future departures
  if (isToday(date)) {
    const futureDepartures = allDepartures.filter(
      dep => dep.scheduledTime >= currentTime
    );
    return futureDepartures.slice(0, count);
  }
  
  // For other days, show the first departures of the day
  return allDepartures.slice(0, count);
}

function isToday(date: Date): boolean {
  const today = new Date();
  return date.toDateString() === today.toDateString();
}