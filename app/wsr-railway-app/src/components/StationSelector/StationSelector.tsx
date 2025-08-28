import React from 'react';
import type { Station } from '../../types/station';
import styles from './StationSelector.module.css';

interface StationSelectorProps {
  stations: Station[];
  selectedStation: Station | null;
  onStationChange: (station: Station) => void;
  label?: string;
}

export const StationSelector: React.FC<StationSelectorProps> = ({
  stations,
  selectedStation,
  onStationChange,
  label = 'Select Station'
}) => {
  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const station = stations.find(s => s.id === event.target.value);
    if (station) {
      onStationChange(station);
    }
  };

  return (
    <div className={styles.selectorContainer}>
      <label className={styles.label} htmlFor="station-select">
        {label}
      </label>
      <div className={styles.selectWrapper}>
        <select
          id="station-select"
          className={styles.select}
          value={selectedStation?.id || ''}
          onChange={handleChange}
        >
          <option value="">Choose a station...</option>
          {stations.map(station => (
            <option key={station.id} value={station.id}>
              {station.name}
              {station.isRequestStop && ' (R)'}
            </option>
          ))}
        </select>
        <div className={styles.selectIcon}>
          <span className={styles.arrow}></span>
        </div>
      </div>
    </div>
  );
};