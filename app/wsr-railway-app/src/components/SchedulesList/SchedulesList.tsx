import React, { useState, useMemo } from 'react';
import styles from './SchedulesList.module.css';
import { serviceCalendar, toDateKey, timetableColors, timetableNames } from '../../services/calendarConfig';
import { getFamilySchedules } from '../../services/timetables';
import { TimetableModal } from '../TimetableModal/TimetableModal';
import type { TimetableType } from '../../services/calendarConfig';
import type { Train } from '../../types/models';

interface SchedulesListProps {
  selectedDate?: Date;
  collapsed?: boolean;
  showFullTimetableLink?: boolean;
}

export const SchedulesList: React.FC<SchedulesListProps> = ({ 
  selectedDate = new Date(), 
  collapsed = false,
  showFullTimetableLink = false 
}) => {
  const [selectedTimetable, setSelectedTimetable] = useState<{
    type: TimetableType;
    trains: Train[];
  } | null>(null);

  // Get available timetable types for the selected month
  const availableTimetables = useMemo(() => {
    const year = selectedDate.getFullYear();
    const month = selectedDate.getMonth();
    const firstDay = new Date(year, month, 1);
    const lastDay = new Date(year, month + 1, 0);
    
    const timetableTypesInMonth = new Set<TimetableType>();
    
    // Check each day in the month
    for (let day = firstDay.getDate(); day <= lastDay.getDate(); day++) {
      const date = new Date(year, month, day);
      const timetableType = serviceCalendar[toDateKey(date)];
      if (timetableType && timetableType !== 'none') {
        timetableTypesInMonth.add(timetableType);
      }
    }
    
    return Array.from(timetableTypesInMonth);
  }, [selectedDate]);

  const allSchedules = useMemo(() => getFamilySchedules(), []);

  // Filter schedules to only show those available in the selected month
  const schedules = allSchedules.filter(schedule => 
    availableTimetables.includes(schedule.type)
  );

  const handleScheduleClick = (schedule: typeof schedules[0]) => {
    setSelectedTimetable({
      type: schedule.type,
      trains: schedule.trains
    });
  };

  if (collapsed || showFullTimetableLink) {
    return (
      <>
        <div className={`${styles.schedulesList} ${styles.sidebarView}`}>
          <h3 className={styles.sidebarTitle}>
            Timetables
          </h3>
          <div className={styles.sidebarContent}>
            {schedules.map((schedule) => (
              <div key={schedule.type} className={styles.sidebarItem}>
                <div 
                  className={styles.sidebarHeader}
                  onClick={() => handleScheduleClick(schedule)}
                >
                  <div 
                    className={styles.sidebarColorBar}
                    style={{ backgroundColor: schedule.color }}
                  />
                  <div className={styles.sidebarInfo}>
                    <div className={styles.sidebarName}>{schedule.name.split(' ')[0]}</div>
                    <div className={styles.sidebarSummary}>
                      {schedule.trains.length} trains
                    </div>
                  </div>
                </div>
                {showFullTimetableLink && (
                  <button 
                    className={styles.viewTimetableBtn}
                    onClick={() => handleScheduleClick(schedule)}
                  >
                    View →
                  </button>
                )}
              </div>
            ))}
            {schedules.length === 0 && (
              <div className={styles.noSchedulesSidebar}>
                No services this month
              </div>
            )}
          </div>
        </div>

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
      </>
    );
  }

  return (
    <>
      <div className={styles.schedulesList}>
        <h3 className={styles.title}>
          Service Schedules 
          <span className={styles.monthIndicator}>
            ({selectedDate.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' })})
          </span>
        </h3>
        {schedules.length > 0 ? (
          <>
            <div className={styles.scheduleCards}>
              {schedules.map((schedule) => (
                <div 
                  key={schedule.type}
                  className={styles.scheduleCard}
                  onClick={() => handleScheduleClick(schedule)}
                  style={{
                    borderLeft: `3px solid ${schedule.color}`
                  }}
                >
                  <div className={styles.cardHeader}>
                    <div 
                      className={styles.colorIndicator}
                      style={{ backgroundColor: schedule.color }}
                    />
                    <div className={styles.cardTitle}>{schedule.name}</div>
                  </div>
                  <div className={styles.cardSummary}>{schedule.summary}</div>
                  <div className={styles.cardActiveDays}>{schedule.activeDays}</div>
                  <button className={styles.viewButton}>
                    View Full Timetable →
                  </button>
                </div>
              ))}
            </div>
            
            <div className={styles.note}>
              Showing schedules active in {selectedDate.toLocaleDateString('en-GB', { month: 'long' })}. 
              Click to view full timetable.
            </div>
          </>
        ) : (
          <div className={styles.noSchedules}>
            No services scheduled for this month.
          </div>
        )}
      </div>

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
    </>
  );
};