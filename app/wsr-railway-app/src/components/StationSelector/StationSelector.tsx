import React from 'react';
import type { Station } from '../../types/models';
import styles from './StationSelector.module.css';

interface StationSelectorProps {
  stations: Station[];
  selectedStation: Station | null;
  onStationChange: (station: Station | null) => void;
  label?: string;
}

export const StationSelector: React.FC<StationSelectorProps> = ({
  stations,
  selectedStation,
  onStationChange,
  label = 'Select Station'
}) => {
  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const station = stations.find(s => s.code === event.target.value);
    onStationChange(station || null);
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
          value={selectedStation?.code || ''}
          onChange={handleChange}
        >
          <option value="">Choose a station...</option>
          {stations.map(station => (
            <option key={station.code} value={station.code}>
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