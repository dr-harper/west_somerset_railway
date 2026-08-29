import { X } from 'lucide-react';
import React from 'react';
import styles from './TimetableModal.module.css';
import type { Train } from '../../types/models';
import { mockStations } from '../../services/mockTrainData';

interface TimetableModalProps {
  isOpen: boolean;
  onClose: () => void;
  trains: Train[];
  timetableType: string;
  timetableName: string;
  timetableColor: string;
}

export const TimetableModal: React.FC<TimetableModalProps> = ({
  isOpen,
  onClose,
  trains,
  timetableName,
  timetableColor
}) => {
  if (!isOpen) return null;

  // Separate northbound and southbound trains
  const northboundTrains = trains.filter(train => 
    train.origin === 'BL' && train.destination === 'MIN'
  );
  const southboundTrains = trains.filter(train => 
    train.origin === 'MIN' && train.destination === 'BL'
  );

  const renderTimetableTable = (trainList: Train[], direction: string) => {
    if (trainList.length === 0) return null;

    return (
      <div className={styles.timetableSection}>
        <h3 className={styles.directionTitle}>{direction}</h3>
        <div className={styles.tableWrapper}>
          <table className={styles.timetableTable}>
            <thead>
              <tr>
                <th>Station</th>
                {trainList.map(train => (
                  <th key={train.id} className={styles.serviceHeader}>
                    <div className={styles.serviceType}>{train.serviceType}</div>
                    <div className={styles.serviceId}>{train.id}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {mockStations.map(station => (
                <tr key={station.code}>
                  <td className={styles.stationName}>{station.name}</td>
                  {trainList.map(train => {
                    const stop = train.stops.find(s => s.stationCode === station.code);
                    if (!stop) {
                      return <td key={`${train.id}-${station.code}`}>-</td>;
                    }
                    return (
                      <td key={`${train.id}-${station.code}`} className={styles.timeCell}>
                        <div className={styles.time}>
                          {stop.scheduledDeparture || stop.scheduledArrival}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <>
      <div className={styles.modalOverlay} onClick={onClose} />
      <div className={styles.modal}>
        <div className={styles.modalHeader}>
          <div className={styles.headerLeft}>
            <div 
              className={styles.timetableIndicator}
              style={{ backgroundColor: timetableColor }}
            />
            <h2 className={styles.modalTitle}>{timetableName} - Full Timetable</h2>
          </div>
          <button className={styles.closeButton} onClick={onClose} aria-label="Close">
            <X size={18} aria-hidden />
          </button>
        </div>
        
        <div className={styles.modalContent}>
          <div className={styles.timetablesContainer}>
            {renderTimetableTable(northboundTrains, 'Northbound: Bishops Lydeard → Minehead')}
            {renderTimetableTable(southboundTrains, 'Southbound: Minehead → Bishops Lydeard')}
          </div>
          
          {trains.length === 0 && (
            <div className={styles.noTrains}>
              No trains scheduled for this timetable type.
            </div>
          )}
        </div>

      </div>
    </>
  );
};