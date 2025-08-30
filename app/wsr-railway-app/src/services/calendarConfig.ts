// West Somerset Railway Calendar Configuration
// Based on the 2025 operating calendar

export type TimetableType = 'blue' | 'red' | 'purple' | 'green' | 'none';

export interface CalendarDay {
  date: string; // YYYY-MM-DD format
  timetableType: TimetableType;
  specialEvent?: string;
}

// Calendar configuration for 2025
// Based on the images provided
export const calendar2025: Record<string, TimetableType> = {
  // For testing - current date
  '2025-08-30': 'blue',  // Today - Blue timetable for testing
  
  // August 2025
  '2025-08-31': 'blue',
  
  // September 2025
  '2025-09-02': 'blue',
  '2025-09-03': 'blue',
  '2025-09-04': 'blue',
  '2025-09-06': 'blue',
  '2025-09-07': 'blue',
  '2025-09-09': 'blue',
  '2025-09-10': 'blue',
  '2025-09-11': 'blue',
  '2025-09-13': 'blue',
  '2025-09-14': 'blue',
  '2025-09-16': 'blue',
  '2025-09-17': 'blue',
  '2025-09-18': 'blue',
  '2025-09-20': 'purple', // Special event
  '2025-09-21': 'purple', // Special event
  '2025-09-23': 'blue',
  '2025-09-24': 'blue',
  '2025-09-25': 'blue',
  '2025-09-27': 'blue',
  '2025-09-28': 'blue',
  '2025-09-30': 'red',
  
  // October 2025
  '2025-10-01': 'red',
  '2025-10-04': 'red',
  '2025-10-05': 'red',
  '2025-10-07': 'red',
  '2025-10-08': 'red',
  '2025-10-11': 'red',
  '2025-10-12': 'red',
  '2025-10-14': 'red',
  '2025-10-15': 'red',
  '2025-10-17': 'purple', // Special event
  '2025-10-18': 'purple', // Special event
  '2025-10-19': 'purple', // Special event
  '2025-10-21': 'red',
  '2025-10-22': 'red',
  '2025-10-25': 'red',
  '2025-10-26': 'red',
  '2025-10-28': 'blue',
  '2025-10-29': 'blue',
  '2025-10-30': 'blue',
  
  // November 2025
  '2025-11-01': 'blue',
  '2025-11-02': 'blue',
  '2025-11-29': 'green', // Christmas services start
  '2025-11-30': 'green',
  
  // December 2025 - Christmas Services
  '2025-12-06': 'green',
  '2025-12-07': 'green',
  '2025-12-13': 'green',
  '2025-12-14': 'green',
  '2025-12-19': 'green',
  '2025-12-20': 'green',
  '2025-12-21': 'green',
  '2025-12-23': 'green',
  '2025-12-24': 'green',
  '2025-12-27': 'green',
  '2025-12-28': 'green',
  '2025-12-29': 'green',
  '2025-12-31': 'green',
};

// Special events configuration
export const specialEvents: Record<string, string> = {
  '2025-09-20': 'Autumn Steam Gala',
  '2025-09-21': 'Autumn Steam Gala',
  '2025-10-17': 'Halloween Special',
  '2025-10-18': 'Halloween Special',
  '2025-10-19': 'Halloween Special',
  '2025-12-06': 'Christmas Services',
  '2025-12-24': 'Christmas Eve Special',
  '2025-12-31': 'New Year\'s Eve Special',
};

// Helper function to get timetable type for a given date
export function getTimetableType(date: Date): TimetableType {
  const dateStr = date.toISOString().split('T')[0];
  return calendar2025[dateStr] || 'none';
}

// Helper function to check if a date has services
export function hasServices(date: Date): boolean {
  const timetableType = getTimetableType(date);
  return timetableType !== 'none';
}

// Helper function to get special event name if applicable
export function getSpecialEvent(date: Date): string | undefined {
  const dateStr = date.toISOString().split('T')[0];
  return specialEvents[dateStr];
}

// Get all dates with a specific timetable type
export function getDatesWithTimetable(timetableType: TimetableType): string[] {
  return Object.entries(calendar2025)
    .filter(([_, type]) => type === timetableType)
    .map(([date]) => date);
}

// Timetable colors for UI
export const timetableColors: Record<TimetableType, string> = {
  blue: '#4A90E2',
  red: '#B32D2E',
  purple: '#8B008B',
  green: '#27AE60',
  none: '#E0E0E0'
};

// Timetable display names
export const timetableNames: Record<TimetableType, string> = {
  blue: 'Blue Timetable',
  red: 'Red Timetable (Enhanced Service)',
  purple: 'Special Event Service',
  green: 'Christmas Services',
  none: 'No Services'
};

// Timetable service summaries
export const timetableSummaries: Record<TimetableType, string> = {
  blue: '4 trains each way • Steam & Diesel • 10:15 first from Bishops Lydeard',
  red: '3 trains each way • Enhanced Steam Service • 10:15 first departure',
  purple: 'Special event trains • Extended stops • Photo opportunities',
  green: 'Festive services • Schedule to be confirmed',
  none: 'No scheduled services'
};