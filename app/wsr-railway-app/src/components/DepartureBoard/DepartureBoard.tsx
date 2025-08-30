import React, { useState, useEffect } from 'react';
import type { DepartureBoard as DepartureBoardType, Departure, StationCode, Train } from '../../types/models';
import { trainService } from '../../services/trainService';
import { JourneyTimeline } from '../JourneyTimeline/JourneyTimeline';
import styles from './DepartureBoard.module.css';

interface DepartureBoardProps {
  stationCode: StationCode | null;
  stationName?: string;
}

export const DepartureBoard: React.FC<DepartureBoardProps> = ({ 
  stationCode,
  stationName 
}) => {
  const [departureBoard, setDepartureBoard] = useState<DepartureBoardType | null>(null);
  const [loading, setLoading] = useState(false);
  const [currentTime, setCurrentTime] = useState(new Date());
  const [expandedTrainId, setExpandedTrainId] = useState<string | null>(null);
  const [expandedTrain, setExpandedTrain] = useState<Train | null>(null);

  useEffect(() => {
    const timer = setInterval(() => {
      setCurrentTime(new Date());
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (stationCode) {
      loadDepartures();
      
      // Subscribe to real-time updates
      const unsubscribe = trainService.onDepartureBoardUpdate(
        stationCode,
        (board) => setDepartureBoard(board)
      );
      
      return () => unsubscribe();
    }
  }, [stationCode]);

  const loadDepartures = async () => {
    if (!stationCode) return;
    
    setLoading(true);
    try {
      const board = await trainService.getDepartureBoard(stationCode);
      setDepartureBoard(board);
    } catch (error) {
      console.error('Failed to load departures:', error);
    } finally {
      setLoading(false);
    }
  };

  const formatTime = (time: string) => {
    return time;
  };

  const getServiceTypeClass = (serviceType: string) => {
    return serviceType.toLowerCase().replace(' ', '');
  };

  const getStatusClass = (status: string) => {
    if (status === 'On Time') return styles.onTime;
    if (status.includes('late')) return styles.delayed;
    if (status === 'Cancelled') return styles.cancelled;
    return '';
  };

  const handleRowClick = async (trainId: string) => {
    if (expandedTrainId === trainId) {
      setExpandedTrainId(null);
      setExpandedTrain(null);
    } else {
      setExpandedTrainId(trainId);
      // Load full train data
      try {
        const train = await trainService.getTrainById(trainId);
        setExpandedTrain(train);
      } catch (error) {
        console.error('Failed to load train details:', error);
      }
    }
  };

  if (!stationCode) {
    return (
      <div className={styles.departureBoard}>
        <div className={styles.noDepartures}>
          Please select a station to view departures
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className={styles.departureBoard}>
        <div className={styles.loading}>Loading departures...</div>
      </div>
    );
  }

  const hour = currentTime.getHours();
  const showingNextDay = hour >= 20 || hour < 10;

  return (
    <div className={styles.departureBoard}>
      <div className={styles.boardHeader}>
        <h2 className={styles.stationName}>{stationName || stationCode}</h2>
        <div className={styles.currentTime}>
          {currentTime.toLocaleTimeString('en-GB', { 
            hour: '2-digit', 
            minute: '2-digit',
            second: '2-digit'
          })}
        </div>
      </div>

      {showingNextDay && (
        <div className={styles.notice}>
          Showing tomorrow's services (today's services have ended)
        </div>
      )}

      {departureBoard && departureBoard.departures.length > 0 ? (
        <table className={styles.departureTable}>
          <thead className={styles.tableHeader}>
            <tr>
              <th>Time</th>
              <th>Destination</th>
              <th>Platform</th>
              <th>Service</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {departureBoard.departures.map((departure: Departure, index: number) => (
              <React.Fragment key={`${departure.trainId}-${index}`}>
                <tr 
                  className={`${styles.departureRow} ${styles.clickable}`}
                  onClick={() => handleRowClick(departure.trainId)}
                >
                  <td className={styles.time}>
                    {formatTime(departure.time)}
                    {expandedTrainId === departure.trainId ? 
                      <span className={styles.expandIcon}>▼</span> : 
                      <span className={styles.expandIcon}>▶</span>
                    }
                  </td>
                  <td className={styles.destination}>
                    {departure.destination}
                  </td>
                  <td className={styles.platform}>
                    {departure.platform || '-'}
                  </td>
                  <td>
                    <span className={`${styles.serviceType} ${styles[getServiceTypeClass(departure.serviceType)]}`}>
                      {departure.serviceType}
                    </span>
                  </td>
                  <td className={`${styles.status} ${getStatusClass(departure.status)}`}>
                    {departure.status}
                  </td>
                </tr>
                {expandedTrainId === departure.trainId && expandedTrain && (
                  <tr className={styles.expandedRow}>
                    <td colSpan={5} className={styles.expandedContent}>
                      <JourneyTimeline train={expandedTrain} selectedStation={stationName} />
                    </td>
                  </tr>
                )}
              </React.Fragment>
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