import React, { useState, useMemo } from 'react';
import styles from './TabbedSchedules.module.css';
import { timetableColors, timetableNames, timetableSummaries, calendar2025 } from '../../services/calendarConfig';
import { blueTimetableTrains, redTimetableTrains, purpleTimetableTrains } from '../../services/timetables';
import { mockStations } from '../../services/mockTrainData';
import type { TimetableType } from '../../services/calendarConfig';
import type { Train } from '../../types/models';

interface TabbedSchedulesProps {
  selectedDate?: Date;
}

export const TabbedSchedules: React.FC<TabbedSchedulesProps> = ({ selectedDate = new Date() }) => {
  const [activeTab, setActiveTab] = useState<TimetableType | null>(null);

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
      const dateStr = date.toISOString().split('T')[0];
      const timetableType = calendar2025[dateStr];
      if (timetableType && timetableType !== 'none') {
        timetableTypesInMonth.add(timetableType);
      }
    }
    
    return Array.from(timetableTypesInMonth);
  }, [selectedDate]);

  const allSchedules = [
    {
      type: 'blue' as TimetableType,
      name: timetableNames.blue,
      summary: timetableSummaries.blue,
      color: timetableColors.blue,
      trains: blueTimetableTrains,
      activeDays: 'Most weekdays and weekends'
    },
    {
      type: 'red' as TimetableType,
      name: timetableNames.red,
      summary: timetableSummaries.red,
      color: timetableColors.red,
      trains: redTimetableTrains,
      activeDays: 'Peak periods and holidays'
    },
    {
      type: 'purple' as TimetableType,
      name: timetableNames.purple,
      summary: timetableSummaries.purple,
      color: timetableColors.purple,
      trains: purpleTimetableTrains,
      activeDays: 'Special event days'
    },
    {
      type: 'green' as TimetableType,
      name: timetableNames.green,
      summary: timetableSummaries.green,
      color: timetableColors.green,
      trains: [], // No trains defined yet for Christmas
      activeDays: 'Festive period'
    }
  ];

  const schedules = allSchedules.filter(schedule => 
    availableTimetables.includes(schedule.type)
  );

  // Set first available tab as active if none selected
  React.useEffect(() => {
    if (!activeTab && schedules.length > 0) {
      setActiveTab(schedules[0].type);
    }
  }, [activeTab, schedules]);

  const renderTimetable = (trains: Train[], direction: string) => {
    const directionTrains = direction === 'northbound' 
      ? trains.filter(train => train.origin === 'BL' && train.destination === 'MIN')
      : trains.filter(train => train.origin === 'MIN' && train.destination === 'BL');

    if (directionTrains.length === 0) return null;

    return (
      <div className={styles.timetableSection}>
        <h4 className={styles.directionTitle}>
          {direction === 'northbound' ? 'Northbound: Bishops Lydeard → Minehead' : 'Southbound: Minehead → Bishops Lydeard'}
        </h4>
        <div className={styles.tableWrapper}>
          <table className={styles.timetableTable}>
            <thead>
              <tr>
                <th className={styles.stationHeader}>Station</th>
                {directionTrains.map(train => (
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
                  {directionTrains.map(train => {
                    const stop = train.stops.find(s => s.stationCode === station.code);
                    if (!stop) {
                      return <td key={`${train.id}-${station.code}`} className={styles.emptyCell}>-</td>;
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

  const renderTimetableTab = (type: TimetableType) => {
    const schedule = schedules.find(s => s.type === type);
    if (!schedule) return null;

    // Special handling for Christmas services with no schedule yet
    if (type === 'green' && schedule.trains.length === 0) {
      return (
        <div className={styles.timetableContent}>
          <div className={styles.timetableHeader}>
            <div 
              className={styles.timetableIndicator}
              style={{ backgroundColor: schedule.color }}
            />
            <h3 className={styles.timetableTitle}>{schedule.name}</h3>
          </div>
          <div className={styles.christmasNotice}>
            <h4>🎄 Christmas Services - Coming Soon!</h4>
            <p>
              We will be running our festive services on the days marked green in the calendar. 
              Please check back on our website for further information which will be released later in the year.
            </p>
            <p className={styles.christmasDates}>
              <strong>Planned service dates:</strong><br/>
              November: 29th, 30th<br/>
              December: 6th, 7th, 13th, 14th, 19th-21st, 23rd, 24th, 27th-29th, 31st
            </p>
          </div>
        </div>
      );
    }

    return (
      <div className={styles.timetableContent}>
        <div className={styles.timetableHeader}>
          <div 
            className={styles.timetableIndicator}
            style={{ backgroundColor: schedule.color }}
          />
          <h3 className={styles.timetableTitle}>{schedule.name}</h3>
        </div>
        <div className={styles.timetablesGrid}>
          {renderTimetable(schedule.trains, 'northbound')}
          {renderTimetable(schedule.trains, 'southbound')}
        </div>
      </div>
    );
  };

  if (schedules.length === 0) {
    return (
      <div className={styles.tabbedSchedules}>
        <div className={styles.noSchedules}>
          No services scheduled for {selectedDate.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' })}.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.tabbedSchedules}>
      <div className={styles.tabs}>
        {schedules.map((schedule) => (
          <button
            key={schedule.type}
            className={`${styles.tab} ${activeTab === schedule.type ? styles.active : ''}`}
            onClick={() => setActiveTab(schedule.type)}
            style={{
              borderBottom: activeTab === schedule.type ? `3px solid ${schedule.color}` : 'none'
            }}
          >
            <div 
              className={styles.tabIndicator}
              style={{ backgroundColor: schedule.color }}
            />
            {schedule.name.split(' ')[0]}
          </button>
        ))}
      </div>
      
      <div className={styles.tabContent}>
        {activeTab && renderTimetableTab(activeTab)}
      </div>
    </div>
  );
};