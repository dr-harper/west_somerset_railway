import { describe, expect, it } from 'vitest';
import {
  getDayInfo,
  getTimetableType,
  hasServices,
  specialEvents,
  timetableSummaries,
  toDateKey
} from './calendarConfig';
import { getTrainsForDate } from './timetables';

describe('toDateKey', () => {
  it('formats in local time, not UTC', () => {
    // BST midnight: toISOString() would give the previous day
    const bstMidnight = new Date(2026, 7, 29, 0, 0, 0);
    expect(toDateKey(bstMidnight)).toBe('2026-08-29');
    expect(bstMidnight.toISOString().slice(0, 10)).toBe('2026-08-28');
  });

  it('pads single-digit months and days', () => {
    expect(toDateKey(new Date(2027, 0, 2))).toBe('2027-01-02');
  });
});

describe('getDayInfo', () => {
  it('classifies a gala day as a purple service day', () => {
    const info = getDayInfo(new Date(2026, 7, 29));
    expect(info.kind).toBe('service');
    expect(info.family).toBe('purple');
    expect(info.patternTitle).toContain('Diesels @ 65');
  });

  it('classifies a closed day', () => {
    const info = getDayInfo(new Date(2026, 7, 28));
    expect(info.kind).toBe('closed');
    expect(hasServices(new Date(2026, 7, 28))).toBe(false);
  });

  it('classifies a Christmas event day', () => {
    const info = getDayInfo(new Date(2026, 11, 5));
    expect(info.kind).toBe('event');
    expect(info.family).toBe('green');
    expect(info.events?.join(' ')).toContain('Santa');
  });

  it('returns unknown beyond the published data', () => {
    expect(getDayInfo(new Date(2027, 5, 1)).kind).toBe('unknown');
    expect(getTimetableType(new Date(2027, 5, 1))).toBe('none');
  });
});

describe('timetable data integrity', () => {
  it('summaries are derived from real data', () => {
    expect(timetableSummaries.yellow).toContain('trains each way');
    expect(timetableSummaries.orange).toContain('DMU');
  });

  it('builds trains for a service day and none for a closed day', () => {
    const galaTrains = getTrainsForDate(new Date(2026, 7, 29));
    expect(galaTrains.length).toBeGreaterThan(15);
    expect(galaTrains.every(t => t.stops.length >= 2)).toBe(true);
    expect(getTrainsForDate(new Date(2026, 7, 28))).toHaveLength(0);
  });

  it('stop times are HH:MM strings in journey order', () => {
    for (const train of getTrainsForDate(new Date(2026, 8, 1))) {
      const times = train.stops
        .map(s => s.scheduledDeparture ?? s.scheduledArrival)
        .filter((t): t is string => Boolean(t));
      expect(times.every(t => /^\d{2}:\d{2}$/.test(t))).toBe(true);
      expect([...times].sort()).toEqual(times);
    }
  });

  it('special events are keyed in local time, not UTC', () => {
    // A BST date built at local midnight reports the previous day through
    // toISOString. ServiceCalendar used that and drew every event marker a
    // square early; toDateKey is what keeps it on the right day.
    const bstDate = new Date(2026, 8, 12);
    expect(bstDate.toISOString().split('T')[0]).toBe('2026-09-11');
    expect(toDateKey(bstDate)).toBe('2026-09-12');
    expect(specialEvents['2026-09-12']).toBeDefined();
  });
});
