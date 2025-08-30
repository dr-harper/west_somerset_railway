import React from 'react';
import styles from './DatePicker.module.css';
import { getTimetableType, timetableColors, timetableNames } from '../../services/calendarConfig';
import type { TimetableType } from '../../services/calendarConfig';

interface DatePickerProps {
  selectedDate: Date;
  onDateChange: (date: Date) => void;
  label?: string;
}

export const DatePicker: React.FC<DatePickerProps> = ({
  selectedDate,
  onDateChange,
  label = 'Travel Date'
}) => {
  const handlePreviousDay = () => {
    const newDate = new Date(selectedDate);
    newDate.setDate(newDate.getDate() - 1);
    onDateChange(newDate);
  };

  const handleNextDay = () => {
    const newDate = new Date(selectedDate);
    newDate.setDate(newDate.getDate() + 1);
    onDateChange(newDate);
  };

  const handleToday = () => {
    onDateChange(new Date());
  };

  const formatDate = (date: Date) => {
    const options: Intl.DateTimeFormatOptions = { 
      weekday: 'short', 
      year: 'numeric', 
      month: 'short', 
      day: 'numeric' 
    };
    return date.toLocaleDateString('en-GB', options);
  };

  const isToday = (date: Date) => {
    const today = new Date();
    return date.toDateString() === today.toDateString();
  };

  const getTimetableInfo = (date: Date): { type: TimetableType; name: string; color: string } => {
    const type = getTimetableType(date);
    return {
      type,
      name: timetableNames[type],
      color: timetableColors[type]
    };
  };

  const timetableInfo = getTimetableInfo(selectedDate);

  return (
    <div className={styles.datePickerContainer}>
      <span className={styles.label}>{label}:</span>
      <div className={styles.dateControls}>
        <button
          className={styles.dateButton}
          onClick={handlePreviousDay}
          aria-label="Previous day"
        >
          ←
        </button>
        <div className={styles.dateDisplay}>
          <div>{formatDate(selectedDate)}</div>
          <div style={{
            fontSize: '11px',
            color: timetableInfo.color,
            fontWeight: '500',
            marginTop: '2px',
            display: 'flex',
            alignItems: 'center',
            gap: '4px'
          }}>
            <span style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: timetableInfo.color,
              display: 'inline-block'
            }}></span>
            {timetableInfo.type === 'none' ? 'No Services' : timetableInfo.name}
          </div>
        </div>
        <button
          className={styles.dateButton}
          onClick={handleNextDay}
          aria-label="Next day"
        >
          →
        </button>
      </div>
      {!isToday(selectedDate) && (
        <button className={styles.todayButton} onClick={handleToday}>
          Today
        </button>
      )}
    </div>
  );
};