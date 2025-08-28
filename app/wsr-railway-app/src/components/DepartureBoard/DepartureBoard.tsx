import React, { useState, useEffect } from 'react';
import type { Departure, ServiceType } from '../../types/train';
import type { Station } from '../../types/station';
import styles from './DepartureBoard.module.css';

interface DepartureBoardProps {
  station: Station;
  departures: Departure[];
}

export const DepartureBoard: React.FC<DepartureBoardProps> = ({ 
  station, 
  departures
}) => {
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const formatTime = (time: string) => {
    return time;
  };

  const getServiceTypeClass = (serviceType: ServiceType) => {
    return serviceType.toLowerCase().replace(' ', '');
  };


  const sortedDepartures = [...departures].sort((a, b) => {
    return a.scheduledTime.localeCompare(b.scheduledTime);
  });

  return (
    <div className={styles.departureBoard}>
      <div className={styles.boardHeader}>
        <h2 className={styles.stationName}>{station.name}</h2>
        <div className={styles.currentTime}>
          {currentTime.toLocaleTimeString('en-GB', { 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
          })}
        </div>
      </div>

      {sortedDepartures.length > 0 ? (
        <table className={styles.departureTable}>
          <thead className={styles.tableHeader}>
            <tr>
              <th>Time</th>
              <th>Destination</th>
              <th>Service</th>
            </tr>
          </thead>
          <tbody>
            {sortedDepartures.map((departure, index) => (
              <tr key={`${departure.train.id}-${index}`} className={styles.departureRow}>
                <td className={styles.time}>
                  {formatTime(departure.scheduledTime)}
                </td>
                <td className={styles.destination}>
                  {departure.destination}
                </td>
                <td>
                  <span className={`${styles.serviceType} ${styles[getServiceTypeClass(departure.serviceType)]}`}>
                    {departure.serviceType}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className={styles.noDepartures}>
          No departures scheduled from this station
        </div>
      )}
    </div>
  );
};