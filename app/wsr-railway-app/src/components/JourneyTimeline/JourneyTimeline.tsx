import { TrainFront } from 'lucide-react';
import React from 'react';
import type { Train, TrainStop } from '../../types/models';
import { SeenAt } from '../SeenAt/SeenAt';
import { sightingFor, type Sighting } from '../../services/sightings';
import { CAMERAS } from '../../services/cameras';
import styles from './JourneyTimeline.module.css';

interface JourneyTimelineProps {
  train: Train;
  currentTime?: string;
  selectedStation?: string;
  /** Today's camera sightings, so each call can show what was observed. */
  sightings?: Sighting[];
}

export const JourneyTimeline: React.FC<JourneyTimelineProps> = ({ train, currentTime, selectedStation, sightings = [] }) => {
  const now = currentTime || new Date().toTimeString().slice(0, 5);
  // Stations that have a camera at all, not stations that happen to have
  // been seen today: a camera that has seen nothing yet should say so,
  // which is different from a station nobody is watching.
  const watched = new Set(
    CAMERAS.map(camera => camera.station).filter(Boolean) as string[]
  );
  
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
                      <TrainFront size={15} aria-hidden /> Train at platform
                    </span>
                  </div>
                )}

                {/* Only where a camera watches: a stop with no camera has
                    nothing to say, and "not seen" would read as a fault
                    rather than an absence of coverage. */}
                {watched.has(stop.stationCode) && (
                  <SeenAt
                    sighting={sightingFor(
                      sightings,
                      stop.stationCode,
                      stop.scheduledDeparture ?? stop.scheduledArrival
                    )}
                    booked={stop.scheduledDeparture ?? stop.scheduledArrival}
                    stationName={stop.stationName}
                  />
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};