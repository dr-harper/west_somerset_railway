import React, { useState, useEffect } from 'react';
import type { Train } from '../../types/models';
import { trainService } from '../../services/trainService';
import styles from './ActiveTrains.module.css';

export const ActiveTrains: React.FC = () => {
  const [activeTrains, setActiveTrains] = useState<Train[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadActiveTrains();
    
    // Update every 30 seconds
    const interval = setInterval(loadActiveTrains, 30000);
    
    return () => clearInterval(interval);
  }, []);

  const loadActiveTrains = async () => {
    try {
      const trains = await trainService.getActiveTrains();
      setActiveTrains(trains.filter(t => t.status.state === 'Running'));
    } catch (error) {
      console.error('Failed to load active trains:', error);
    } finally {
      setLoading(false);
    }
  };

  const getLocationDisplay = (train: Train): string => {
    if (train.currentLocation?.at) {
      const station = train.stops.find(s => s.stationCode === train.currentLocation?.at);
      return `At ${station?.stationName || train.currentLocation.at}`;
    }
    if (train.currentLocation?.between) {
      const [from, to] = train.currentLocation.between;
      const fromStation = train.stops.find(s => s.stationCode === from);
      const toStation = train.stops.find(s => s.stationCode === to);
      return `Between ${fromStation?.stationName || from} and ${toStation?.stationName || to}`;
    }
    return 'Location unknown';
  };

  const getNextStop = (train: Train): string => {
    const currentTime = new Date().toTimeString().slice(0, 5);
    const nextStop = train.stops.find(stop => 
      stop.scheduledArrival && stop.scheduledArrival > currentTime && stop.status !== 'Departed'
    );
    return nextStop ? `Next: ${nextStop.stationName} at ${nextStop.scheduledArrival}` : 'Completing journey';
  };

  if (loading) {
    return <div className={styles.loading}>Loading active trains...</div>;
  }

  if (activeTrains.length === 0) {
    return (
      <div className={styles.noTrains}>
        No trains currently running. Services operate from 10:00 to 18:00.
      </div>
    );
  }

  return (
    <div className={styles.activeTrains}>
      <h2 className={styles.title}>Currently Running Trains</h2>
      <div className={styles.trainList}>
        {activeTrains.map(train => (
          <div key={train.id} className={styles.trainCard}>
            <div className={styles.trainHeader}>
              <span className={styles.trainId}>{train.id}</span>
              <span className={`${styles.serviceType} ${styles[train.serviceType.toLowerCase()]}`}>
                {train.serviceType}
              </span>
            </div>
            <div className={styles.trainRoute}>
              <span className={styles.origin}>{train.stops[0].stationName}</span>
              <span className={styles.arrow}>→</span>
              <span className={styles.destination}>
                {train.stops[train.stops.length - 1].stationName}
              </span>
            </div>
            <div className={styles.trainStatus}>
              <div className={styles.location}>{getLocationDisplay(train)}</div>
              <div className={styles.nextStop}>{getNextStop(train)}</div>
              {train.status.delayMinutes > 0 && (
                <div className={styles.delay}>
                  Running {train.status.delayMinutes} minutes late
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};