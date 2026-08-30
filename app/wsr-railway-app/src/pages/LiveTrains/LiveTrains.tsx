import { MapPin, TrainFront } from 'lucide-react';
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { RouteMap } from '../../components/RouteMap/RouteMap';
import { TrackMap } from '../../components/TrackMap/TrackMap';
import { trainService } from '../../services/trainService';
import type { Train, Station } from '../../types/models';
import styles from './LiveTrains.module.css';

export const LiveTrains: React.FC = () => {
  const [trains, setTrains] = useState<Train[]>([]);
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedTrain, setSelectedTrain] = useState<Train | null>(null);

  async function loadData() {
    try {
      const [allTrains, allStations] = await Promise.all([
        trainService.getActiveTrains(),
        trainService.getAllStations()
      ]);
      setTrains(allTrains);
      setStations(allStations);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  // Taken from today's actual timetable rather than asserted. The page
  // claimed "10:00 to 18:00", which is wrong on any gala day — today's
  // first booked departure is 08:10 and the last 18:25.
  const bookedTimes = trains
    .flatMap(t => t.stops.map(s => s.scheduledDeparture ?? s.scheduledArrival))
    .filter((t): t is string => Boolean(t))
    .sort();
  const firstDeparture = bookedTimes[0];
  const lastDeparture = bookedTimes[bookedTimes.length - 1];

  const runningTrains = trains.filter(t => t.status.state === 'Running');
  const upcomingTrains = trains.filter(t => {
    if (t.status.state !== 'Scheduled') return false;
    const now = new Date();
    const currentTime = now.toTimeString().slice(0, 5);
    const firstDeparture = t.stops[0].scheduledDeparture;
    if (!firstDeparture) return false;
    
    const [currentHour, currentMin] = currentTime.split(':').map(Number);
    const [depHour, depMin] = firstDeparture.split(':').map(Number);
    const currentMinutes = currentHour * 60 + currentMin;
    const depMinutes = depHour * 60 + depMin;
    const diffMinutes = depMinutes - currentMinutes;
    const adjustedDiff = diffMinutes < 0 ? diffMinutes + 1440 : diffMinutes;
    
    return adjustedDiff > 0 && adjustedDiff <= 120; // Next 2 hours
  });

  const getTrainLocation = (train: Train): string => {
    if (!train.currentLocation) return 'Unknown';
    
    if (train.currentLocation.at) {
      const station = stations.find(s => s.code === train.currentLocation!.at);
      return `At ${station?.name || train.currentLocation.at}`;
    }
    
    if (train.currentLocation.between) {
      const [from, to] = train.currentLocation.between;
      const fromStation = stations.find(s => s.code === from);
      const toStation = stations.find(s => s.code === to);
      return `Between ${fromStation?.name || from} and ${toStation?.name || to}`;
    }
    
    return 'In transit';
  };

  const getNextStop = (train: Train): string => {
    const nextStop = train.stops.find(s => s.status === 'Scheduled');
    if (!nextStop) return 'Journey completing';
    return `${nextStop.stationName} at ${nextStop.scheduledArrival || nextStop.scheduledDeparture}`;
  };

  if (loading) {
    return (
      <div className={styles.container}>
        <div className={styles.loading}>Loading live train information...</div>
      </div>
    );
  }

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <Link to="/" className={styles.backLink}>← Back to Departures</Link>
        <h1>Trains today</h1>
        <div className={styles.updateTime}>
          Positions estimated from the timetable ·{' '}
          {new Date().toLocaleTimeString('en-GB')}
        </div>
      </div>

      <RouteMap trains={trains} stations={stations} />
      
      <TrackMap stations={stations} trains={trains} />

      <div className={styles.trainLists}>
        {runningTrains.length > 0 && (
          <div className={styles.section}>
            <h2 className={styles.sectionTitle}>
              Due to be running ({runningTrains.length})
            </h2>
            <div className={styles.trainGrid}>
              {runningTrains.map(train => (
                <div 
                  key={train.id} 
                  className={`${styles.trainCard} ${selectedTrain?.id === train.id ? styles.selected : ''}`}
                  onClick={() => setSelectedTrain(train)}
                >
                  <div className={styles.trainHeader}>
                    <span className={styles.trainId}>{train.id}</span>
                    <span className={`${styles.serviceType} ${styles[train.serviceType.toLowerCase()]}`}>
                      {train.serviceType}
                    </span>
                  </div>
                  
                  <div className={styles.trainRoute}>
                    {train.stops[0].stationName} → {train.stops[train.stops.length - 1].stationName}
                  </div>
                  
                  <div className={styles.trainLocation}>
                    <MapPin className={styles.locationIcon} size={15} aria-hidden />
                    {getTrainLocation(train)}
                  </div>
                  
                  <div className={styles.trainNext}>
                    Next: {getNextStop(train)}
                  </div>
                  
                  {train.status.delayMinutes > 0 && (
                    <div className={styles.delay}>
                      Running {train.status.delayMinutes} minutes late
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {upcomingTrains.length > 0 && (
          <div className={styles.section}>
            <h2 className={styles.sectionTitle}>
              Departing Soon ({upcomingTrains.length})
            </h2>
            <div className={styles.upcomingGrid}>
              {upcomingTrains.map(train => (
                <div key={train.id} className={styles.upcomingCard}>
                  <div className={styles.upcomingHeader}>
                    <span className={styles.trainId}>{train.id}</span>
                    <span className={`${styles.serviceType} ${styles[train.serviceType.toLowerCase()]}`}>
                      {train.serviceType}
                    </span>
                  </div>
                  <div className={styles.upcomingRoute}>
                    {train.stops[0].stationName} → {train.stops[train.stops.length - 1].stationName}
                  </div>
                  <div className={styles.upcomingTime}>
                    Departs: {train.stops[0].scheduledDeparture}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {runningTrains.length === 0 && upcomingTrains.length === 0 && (
          <div className={styles.noTrains}>
            <TrainFront className={styles.noTrainsIcon} size={32} aria-hidden />
            <p>No trains due to be running just now.</p>
            {firstDeparture && lastDeparture ? (
              <p>Today's service runs from {firstDeparture} to {lastDeparture}.</p>
            ) : (
              <p>No services are booked today.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};