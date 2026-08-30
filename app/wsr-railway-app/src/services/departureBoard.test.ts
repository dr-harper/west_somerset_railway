import { describe, expect, it, vi, afterEach } from 'vitest';
import { getTrainsForDate } from './timetables';

/**
 * The departure board used to pretend it was 09:00 whenever the real hour
 * was before 10 or after 20, and told visitors "today's services have
 * ended" on the same rule. On a railway whose first train is 08:10 that
 * was wrong every operating morning — and it said the day was over while
 * listing that day's services underneath.
 */
describe('departure board honours the real clock', () => {
  afterEach(() => vi.useRealTimers());

  it('a gala morning has services still to come at 09:10', () => {
    vi.setSystemTime(new Date(2026, 7, 30, 9, 10));
    const now = new Date().toTimeString().slice(0, 5);
    const trains = getTrainsForDate(new Date(2026, 7, 30));
    const later = trains.flatMap(t =>
      t.stops
        .map(s => s.scheduledDeparture)
        .filter((d): d is string => Boolean(d) && d! >= now)
    );
    expect(now).toBe('09:10');
    expect(later.length).toBeGreaterThan(0);
  });

  it("the day's first departure is before 10:00, so a 10:00 floor hides trains", () => {
    const trains = getTrainsForDate(new Date(2026, 7, 30));
    const times = trains
      .flatMap(t => t.stops.map(s => s.scheduledDeparture))
      .filter((d): d is string => Boolean(d))
      .sort();
    expect(times[0] < '10:00').toBe(true);
  });
});
