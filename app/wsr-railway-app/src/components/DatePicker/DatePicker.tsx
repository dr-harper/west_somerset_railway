import React, { useState, useEffect } from 'react';
import styles from './DatePicker.module.css';

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
  const [currentMonth, setCurrentMonth] = useState(
    new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1)
  );
  const [trainCounts, setTrainCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    const daysInMonth = new Date(
      currentMonth.getFullYear(),
      currentMonth.getMonth() + 1,
      0
    ).getDate();
    const counts: Record<string, number> = {};
    for (let day = 1; day <= daysInMonth; day++) {
      const key = `${currentMonth.getFullYear()}-${currentMonth.getMonth()}-${day}`;
      counts[key] = Math.floor(Math.random() * 11);
    }
    setTrainCounts(counts);
  }, [currentMonth]);

  useEffect(() => {
    setCurrentMonth(
      new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1)
    );
  }, [selectedDate]);

  const handlePrevMonth = () => {
    setCurrentMonth(
      new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1)
    );
  };

  const handleNextMonth = () => {
    setCurrentMonth(
      new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1)
    );
  };

  const handleToday = () => {
    onDateChange(new Date());
  };

  const handleDateClick = (date: Date) => {
    onDateChange(date);
  };

  const formatMonthYear = (date: Date) =>
    date.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' });

  const startDay = (() => {
    const day = new Date(
      currentMonth.getFullYear(),
      currentMonth.getMonth(),
      1
    ).getDay();
    return (day + 6) % 7; // Monday start
  })();

  const daysInMonth = new Date(
    currentMonth.getFullYear(),
    currentMonth.getMonth() + 1,
    0
  ).getDate();

  const weeks: (Date | null)[][] = [];
  let dayCounter = 1 - startDay;

  while (dayCounter <= daysInMonth) {
    const week: (Date | null)[] = [];
    for (let i = 0; i < 7; i++) {
      if (dayCounter > 0 && dayCounter <= daysInMonth) {
        week.push(
          new Date(currentMonth.getFullYear(), currentMonth.getMonth(), dayCounter)
        );
      } else {
        week.push(null);
      }
      dayCounter++;
    }
    weeks.push(week);
  }

  const dateKey = (date: Date) =>
    `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;

  const getColor = (count: number) => {
    const hue = (count / 10) * 120;
    return `hsl(${hue}, 70%, 85%)`;
  };

  return (
    <div className={styles.datePickerContainer}>
      <span className={styles.label}>{label}:</span>
      <div className={styles.calendarWrapper}>
        <div className={styles.calendarHeader}>
          <button
            className={styles.navButton}
            onClick={handlePrevMonth}
            aria-label="Previous month"
          >
            ←
          </button>
          <div className={styles.monthLabel}>
            {formatMonthYear(currentMonth)}
          </div>
          <button
            className={styles.navButton}
            onClick={handleNextMonth}
            aria-label="Next month"
          >
            →
          </button>
        </div>
        <table className={styles.calendar}>
          <thead>
            <tr>
              {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map(day => (
                <th key={day}>{day}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {weeks.map((week, i) => (
              <tr key={i}>
                {week.map((date, j) => {
                  if (!date) {
                    return <td key={j}></td>;
                  }
                  const key = dateKey(date);
                  const count = trainCounts[key] ?? 0;
                  const isSelected =
                    date.toDateString() === selectedDate.toDateString();
                  return (
                    <td key={j}>
                      <button
                        className={`${styles.dayButton} ${
                          isSelected ? styles.selected : ''
                        }`}
                        style={{ backgroundColor: getColor(count) }}
                        onClick={() => handleDateClick(date)}
                      >
                        <span className={styles.dayNumber}>
                          {date.getDate()}
                        </span>
                        <span className={styles.trainCount}>{count}</span>
                      </button>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
        {!(selectedDate.toDateString() === new Date().toDateString()) && (
          <button className={styles.todayButton} onClick={handleToday}>
            Today
          </button>
        )}
      </div>
    </div>
  );
};

