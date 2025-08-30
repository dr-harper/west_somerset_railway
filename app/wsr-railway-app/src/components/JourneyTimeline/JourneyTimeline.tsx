import React from 'react';
import type { Train, TrainStop } from '../../types/models';
import styles from './JourneyTimeline.module.css';

interface JourneyTimelineProps {
  train: Train;
  currentTime?: string;
  selectedStation?: string;
}

export const JourneyTimeline: React.FC<JourneyTimelineProps> = ({ train, currentTime, selectedStation }) => {
  const now = currentTime || new Date().toTimeString().slice(0, 5);
  
  const getStopStatus = (stop: TrainStop): 'passed' | 'current' | 'upcoming' => {
    if (stop.status === 'Departed') return 'passed';
    if (stop.status === 'Arrived') return 'current';
    
    // Check by time if status not set
    if (stop.scheduledDeparture && now > stop.scheduledDeparture) {
      return 'passed';
    }
    if (stop.scheduledArrival && now >= stop.scheduledArrival && 
        stop.scheduledDeparture && now < stop.scheduledDeparture) {
      return 'current';
    }
    return 'upcoming';
  };

  const getDelayDisplay = (delayMinutes?: number): string | null => {
    if (!delayMinutes || delayMinutes === 0) return null;
    if (delayMinutes > 0) return `+${delayMinutes}`;
    return delayMinutes.toString();
  };

  const calculateJourneyDuration = (): string => {
    const firstDeparture = train.stops[0].scheduledDeparture;
    const lastArrival = train.stops[train.stops.length - 1].scheduledArrival;
    
    if (!firstDeparture || !lastArrival) return '';
    
    const [startH, startM] = firstDeparture.split(':').map(Number);
    const [endH, endM] = lastArrival.split(':').map(Number);
    
    const totalMinutes = (endH * 60 + endM) - (startH * 60 + startM);
    const hours = Math.floor(totalMinutes / 60);
    const minutes = totalMinutes % 60;
    
    if (hours > 0) {
      return `${hours}h ${minutes}m`;
    }
    return `${minutes}m`;
  };

  return (
    <div className={styles.timeline}>
      <div className={styles.header}>
        <div className={styles.trainInfo}>
          <span className={styles.trainId}>{train.id}</span>
          <span className={`${styles.serviceType} ${styles[train.serviceType.toLowerCase()]}`}>
            {train.serviceType}
          </span>
          {train.notes && <span className={styles.notes}>{train.notes}</span>}
        </div>
        <div className={styles.journeyInfo}>
          <span className={styles.duration}>Journey time: {calculateJourneyDuration()}</span>
          {train.status.delayMinutes > 0 && (
            <span className={styles.delayBadge}>
              Running {train.status.delayMinutes} min late
            </span>
          )}
        </div>
      </div>

      <div className={styles.stopsContainer}>
        <div className={styles.line} />
        
        {/* Train position indicator when between stations */}
        {train.currentLocation?.between && (() => {
          const [fromCode, toCode] = train.currentLocation.between;
          const fromIndex = train.stops.findIndex(s => s.stationCode === fromCode);
          const toIndex = train.stops.findIndex(s => s.stationCode === toCode);
          if (fromIndex !== -1 && toIndex !== -1) {
            // Calculate vertical position between the two stations
            const topPosition = ((fromIndex + toIndex) / 2) / (train.stops.length - 1) * 100;
            return (
              <div 
                className={styles.trainBetweenStations} 
                style={{ top: `${topPosition}%` }}
              >
                <div className={styles.trainDot}>
                  <div className={styles.trainPulse} />
                </div>
              </div>
            );
          }
          return null;
        })()}
        
        {train.stops.map((stop, index) => {
          const status = getStopStatus(stop);
          const isFirst = index === 0;
          const isLast = index === train.stops.length - 1;
          const delay = getDelayDisplay(stop.delayMinutes);
          
          const isSelectedStation = selectedStation === stop.stationName;
          const isAtStation = train.currentLocation?.at === stop.stationCode;
          
          return (
            <div key={`${stop.stationCode}-${index}`} className={`${styles.stop} ${styles[status]} ${isSelectedStation ? styles.selected : ''}`}>
              <div className={styles.stopDot}>
                {isAtStation && <div className={styles.currentLocationPulse} />}
                {isSelectedStation && <div className={styles.selectedRing} />}
              </div>
              
              <div className={styles.stopContent}>
                <div className={styles.stopLine}>
                  <span className={styles.stationName}>
                    {stop.stationName}
                    {stop.isRequestStop && <span className={styles.requestStop}> (R)</span>}
                  </span>
                  <span className={styles.time}>
                    {isFirst ? stop.scheduledDeparture : 
                     isLast ? stop.scheduledArrival :
                     stop.scheduledArrival || stop.scheduledDeparture}
                    {delay && <span className={styles.delay}> {delay}</span>}
                  </span>
                </div>
                
                {isAtStation && (
                  <div className={styles.currentStatus}>
                    <span className={styles.trainLocation}>
                      🚂 Train at platform
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};