import React from 'react';
import type { Train, Station } from '../../types/models';
import styles from './RouteMap.module.css';

interface RouteMapProps {
  trains: Train[];
  stations: Station[];
}

export const RouteMap: React.FC<RouteMapProps> = ({ trains, stations }) => {
  // Calculate position along the route (0-100%)
  const getTrainPosition = (train: Train): number => {
    if (!train.currentLocation) return 0;
    
    const totalStops = train.stops.length;
    let currentStopIndex = 0;
    
    if (train.currentLocation.at) {
      currentStopIndex = train.stops.findIndex(s => s.stationCode === train.currentLocation!.at);
    } else if (train.currentLocation.between) {
      currentStopIndex = train.stops.findIndex(s => s.stationCode === train.currentLocation!.between![0]);
      currentStopIndex += 0.5; // Halfway between stations
    }
    
    return (currentStopIndex / (totalStops - 1)) * 100;
  };
  
  const getDirectionClass = (train: Train): string => {
    // Northbound: BL to MIN, Southbound: MIN to BL
    return train.origin === 'BL' ? 'northbound' : 'southbound';
  };
  
  const runningTrains = trains.filter(t => t.status.state === 'Running');
  
  return (
    <div className={styles.routeMap}>
      <div className={styles.mapHeader}>
        <h3>Live Route Map</h3>
        <div className={styles.legend}>
          <div className={styles.legendItem}>
            <div className={`${styles.trainIcon} ${styles.northbound}`}>▶</div>
            <span>Northbound</span>
          </div>
          <div className={styles.legendItem}>
            <div className={`${styles.trainIcon} ${styles.southbound}`}>◀</div>
            <span>Southbound</span>
          </div>
          <div className={styles.legendItem}>
            <div className={`${styles.stationDot}`}></div>
            <span>Station</span>
          </div>
        </div>
      </div>
      
      <div className={styles.routeContainer}>
        {/* Main railway line */}
        <div className={styles.railwayLine}>
          <div className={styles.track} />
          <div className={styles.trackSleepers} />
        </div>
        
        {/* Station markers */}
        <div className={styles.stations}>
          {stations.map((station, index) => {
            const position = (index / (stations.length - 1)) * 100;
            return (
              <div
                key={station.code}
                className={styles.station}
                style={{ left: `${position}%` }}
              >
                <div className={styles.stationDot} />
                <div className={styles.stationName}>
                  {station.name.length > 10 ? station.code : station.name}
                  {station.isRequestStop && <span className={styles.requestStop}> (R)</span>}
                </div>
                <div className={styles.stationCode}>{station.code}</div>
              </div>
            );
          })}
        </div>
        
        {/* Train positions */}
        <div className={styles.trains}>
          {runningTrains.map(train => {
            const position = getTrainPosition(train);
            const direction = getDirectionClass(train);
            const isDelayed = train.status.delayMinutes > 0;
            
            return (
              <div
                key={train.id}
                className={`${styles.train} ${styles[direction]} ${isDelayed ? styles.delayed : ''}`}
                style={{ left: `${position}%` }}
              >
                <div className={styles.trainIcon}>
                  {direction === 'northbound' ? '▶' : '◀'}
                </div>
                <div className={styles.trainInfo}>
                  <div className={styles.trainId}>{train.id}</div>
                  <div className={styles.trainType}>
                    {train.serviceType}
                  </div>
                  {isDelayed && (
                    <div className={styles.delay}>+{train.status.delayMinutes}</div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
        
        {/* Distance scale */}
        <div className={styles.distanceScale}>
          <div className={styles.scaleMarker} style={{ left: '0%' }}>0 miles</div>
          <div className={styles.scaleMarker} style={{ left: '25%' }}>5.5 miles</div>
          <div className={styles.scaleMarker} style={{ left: '50%' }}>11 miles</div>
          <div className={styles.scaleMarker} style={{ left: '75%' }}>16.5 miles</div>
          <div className={styles.scaleMarker} style={{ left: '100%' }}>22 miles</div>
        </div>
      </div>
      
      {runningTrains.length === 0 && (
        <div className={styles.noTrains}>
          No trains currently running on the line
        </div>
      )}
    </div>
  );
};