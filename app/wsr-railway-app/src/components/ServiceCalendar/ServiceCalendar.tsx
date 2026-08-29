import React, { useState, useMemo } from 'react';
import styles from './ServiceCalendar.module.css';
import { serviceCalendar, toDateKey, getTimetableType, timetableColors, specialEvents, timetableNames, timetableSummaries } from '../../services/calendarConfig';
import type { TimetableType } from '../../services/calendarConfig';
import type { Train } from '../../types/models';
import { TimetableModal } from '../TimetableModal/TimetableModal';
import { getTrainsForTimetable } from '../../services/timetables';

interface ServiceCalendarProps {
  onDateSelect?: (date: Date) => void;
  selectedDate?: Date;
  currentViewMonth?: Date;
  onMonthChange?: (month: Date) => void;
}

export const ServiceCalendar: React.FC<ServiceCalendarProps> = ({ 
  onDateSelect,
  selectedDate,
  currentViewMonth,
  onMonthChange
}) => {
  const today = new Date();
  const currentMonthStart = new Date(today.getFullYear(), today.getMonth(), 1);
  
  const [currentMonth, setCurrentMonth] = useState(() => {
    const date = currentViewMonth || selectedDate || new Date();
    return new Date(date.getFullYear(), date.getMonth(), 1);
  });

  const [selectedTimetable, setSelectedTimetable] = useState<{
    type: TimetableType;
    trains: Train[];
  } | null>(null);

  React.useEffect(() => {
    if (currentViewMonth) {
      setCurrentMonth(currentViewMonth);
    }
  }, [currentViewMonth]);

  // Get available timetables for the current 3-month view
  const availableTimetables = useMemo(() => {
    const timetableTypesInView = new Set<TimetableType>();
    
    // Check all three months
    for (let monthOffset = 0; monthOffset < 3; monthOffset++) {
      const checkMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + monthOffset, 1);
      const lastDay = new Date(checkMonth.getFullYear(), checkMonth.getMonth() + 1, 0);
      
      for (let day = 1; day <= lastDay.getDate(); day++) {
        const date = new Date(checkMonth.getFullYear(), checkMonth.getMonth(), day);
        const timetableType = serviceCalendar[toDateKey(date)];
        if (timetableType && timetableType !== 'none') {
          timetableTypesInView.add(timetableType);
        }
      }
    }
    
    return Array.from(timetableTypesInView);
  }, [currentMonth]);

  const scheduleData = (type: TimetableType) =>
    type === 'green' || type === 'none' ? [] : getTrainsForTimetable(type);

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const getDaysInMonth = (date: Date) => {
    return new Date(date.getFullYear(), date.getMonth() + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (date: Date) => {
    return new Date(date.getFullYear(), date.getMonth(), 1).getDay();
  };

  // Check if we can go back (prevent going before current month)
  const canGoBack = currentMonth.getTime() > currentMonthStart.getTime();

  const handlePreviousMonth = () => {
    if (!canGoBack) return;
    
    const newMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 3, 1);
    // Make sure we don't go before the current month
    if (newMonth.getTime() < currentMonthStart.getTime()) {
      setCurrentMonth(currentMonthStart);
      if (onMonthChange) {
        onMonthChange(currentMonthStart);
      }
    } else {
      setCurrentMonth(newMonth);
      if (onMonthChange) {
        onMonthChange(newMonth);
      }
    }
  };

  const handleNextMonth = () => {
    const newMonth = new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 3, 1);
    setCurrentMonth(newMonth);
    if (onMonthChange) {
      onMonthChange(newMonth);
    }
  };

  const isSelectedDate = (day: number, monthDate: Date) => {
    if (!selectedDate) return false;
    return (
      selectedDate.getDate() === day &&
      selectedDate.getMonth() === monthDate.getMonth() &&
      selectedDate.getFullYear() === monthDate.getFullYear()
    );
  };

  const isToday = (day: number, monthDate: Date) => {
    const today = new Date();
    return (
      today.getDate() === day &&
      today.getMonth() === monthDate.getMonth() &&
      today.getFullYear() === monthDate.getFullYear()
    );
  };

  const getTimetableForDay = (day: number, monthDate: Date): TimetableType => {
    const date = new Date(monthDate.getFullYear(), monthDate.getMonth(), day);
    return getTimetableType(date);
  };

  const getSpecialEventForDay = (day: number, monthDate: Date): string | undefined => {
    const date = new Date(monthDate.getFullYear(), monthDate.getMonth(), day);
    const dateStr = date.toISOString().split('T')[0];
    return specialEvents[dateStr];
  };

  const renderMonthCalendar = (monthDate: Date) => {
    const daysInMonth = getDaysInMonth(monthDate);
    const firstDay = getFirstDayOfMonth(monthDate);
    const days = [];

    // Empty cells for days before month starts
    for (let i = 0; i < firstDay; i++) {
      days.push(
        <div key={`empty-${i}`} className={styles.emptyDay}></div>
      );
    }

    // Days of the month
    for (let day = 1; day <= daysInMonth; day++) {
      const timetableType = getTimetableForDay(day, monthDate);
      const specialEvent = getSpecialEventForDay(day, monthDate);
      const color = timetableColors[timetableType];
      
      days.push(
        <div
          key={day}
          className={`${styles.calendarDay} ${
            isSelectedDate(day, monthDate) ? styles.selected : ''
          } ${isToday(day, monthDate) ? styles.today : ''} ${
            timetableType !== 'none' ? styles.hasService : ''
          }`}
          onClick={() => {
            const date = new Date(monthDate.getFullYear(), monthDate.getMonth(), day);
            if (onDateSelect) {
              onDateSelect(date);
            }
          }}
          style={{
            backgroundColor: timetableType !== 'none' ? color + '20' : 'transparent',
            borderColor: isSelectedDate(day, monthDate) ? color : 'transparent',
            borderWidth: isSelectedDate(day, monthDate) ? '2px' : '1px',
            cursor: timetableType !== 'none' ? 'pointer' : 'default'
          }}
          title={specialEvent || (timetableType !== 'none' ? `${timetableType} timetable` : 'No services')}
        >
          <div className={styles.dayNumber}>{day}</div>
          {timetableType !== 'none' && (
            <div 
              className={styles.serviceIndicator}
              style={{ backgroundColor: color }}
            />
          )}
          {specialEvent && (
            <div className={styles.specialEventIndicator} title={specialEvent}>
              ✨
            </div>
          )}
        </div>
      );
    }

    return days;
  };

  const renderSingleMonth = (monthDate: Date, showHeader = true) => (
    <div className={styles.monthContainer}>
      {showHeader && (
        <h4 className={styles.monthName}>
          {monthNames[monthDate.getMonth()]} {monthDate.getFullYear()}
        </h4>
      )}
      <div className={styles.weekDaysCompact}>
        <div>S</div>
        <div>M</div>
        <div>T</div>
        <div>W</div>
        <div>T</div>
        <div>F</div>
        <div>S</div>
      </div>
      <div className={styles.calendarGrid}>
        {renderMonthCalendar(monthDate)}
      </div>
    </div>
  );

  return (
    <div className={styles.calendar}>
      <div className={styles.calendarHeader}>
        {canGoBack ? (
          <button 
            onClick={handlePreviousMonth}
            className={styles.monthButton}
            aria-label="Previous 3 months"
            title="Previous 3 months"
          >
            ←
          </button>
        ) : (
          <div className={styles.monthButtonPlaceholder} />
        )}
        <h3 className={styles.monthTitle}>
          {monthNames[currentMonth.getMonth()]} {currentMonth.getFullYear()} - {monthNames[(currentMonth.getMonth() + 2) % 12]} {currentMonth.getMonth() > 9 ? currentMonth.getFullYear() + 1 : currentMonth.getFullYear()}
        </h3>
        <button 
          onClick={handleNextMonth}
          className={styles.monthButton}
          aria-label="Next 3 months"
          title="Next 3 months"
        >
          →
        </button>
      </div>
      
      <div className={styles.multiMonthGrid}>
        {renderSingleMonth(currentMonth, true)}
        {renderSingleMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1), true)}
        {renderSingleMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 2, 1), true)}
      </div>
      
      {/* Schedule Overview Footer */}
      {availableTimetables.length > 0 && (
        <div className={styles.scheduleFooter}>
          <h4 className={styles.footerTitle}>Available Services</h4>
          <div className={styles.scheduleCards}>
            {availableTimetables.map(type => (
              <div 
                key={type}
                className={styles.scheduleCard}
                style={{ borderColor: timetableColors[type] }}
              >
                <div className={styles.cardHeader}>
                  <div 
                    className={styles.colorDot}
                    style={{ backgroundColor: timetableColors[type] }}
                  />
                  <span className={styles.scheduleName}>{timetableNames[type]}</span>
                </div>
                <p className={styles.scheduleSummary}>{timetableSummaries[type]}</p>
                <button
                  className={styles.viewTimetableBtn}
                  onClick={() => setSelectedTimetable({
                    type,
                    trains: scheduleData(type)
                  })}
                  style={{ color: timetableColors[type] }}
                >
                  View Full Timetable →
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timetable Modal */}
      {selectedTimetable && (
        <TimetableModal
          isOpen={true}
          onClose={() => setSelectedTimetable(null)}
          trains={selectedTimetable.trains}
          timetableType={selectedTimetable.type}
          timetableName={timetableNames[selectedTimetable.type]}
          timetableColor={timetableColors[selectedTimetable.type]}
        />
      )}
    </div>
  );
};