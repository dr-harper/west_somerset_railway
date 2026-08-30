import { describe, expect, it } from 'vitest';
import { groupSightings, sightingFor } from '../../src/services/sightings';
import type { Episode } from '../../src/utils/firestore/episodes';

const ep = (camera: string, enter: string, exit: string): Episode =>
  ({ id: `${enter}_${camera}`, camera, t_enter: `2026-08-30T${enter}`,
     t_exit: `2026-08-30T${exit}`, date_key: '2026-08-30', direction: null,
     zones: [], peak_conf: 0.9, keyframe: null, hires: null,
     claim: { kind: 'unscheduled', booked_departure: null, serviceType: null,
              loco: null, delay_min: null, corroborating_sightings: null },
     status: 'unverified', verification: null }) as Episode;

describe('sightings', () => {
  it('merges two cameras at one station into a single train', () => {
    // Williton this morning: both cameras saw the same train stand in the loop.
    const s = groupSightings([
      ep('williton', '08:46:29', '08:59:18'),
      ep('williton_2', '08:45:49', '09:00:02'),
    ]);
    expect(s).toHaveLength(1);
    expect(s[0].station).toBe('WIL');
    expect(s[0].cameras).toHaveLength(2);
    expect(s[0].firstSeen).toContain('08:45:49');   // earliest arrival
    expect(s[0].lastSeen).toContain('09:00:02');    // latest departure
    expect(s[0].dwellSeconds).toBeGreaterThan(800);
  });

  it('keeps trains far apart at one station separate', () => {
    const s = groupSightings([
      ep('watchet_1', '08:38:14', '08:40:43'),
      ep('watchet_1', '09:04:48', '09:07:22'),
    ]);
    expect(s).toHaveLength(2);
  });

  it('matches a booked time and reports how late it was', () => {
    const s = groupSightings([ep('williton', '10:07:00', '10:09:00')]);
    const hit = sightingFor(s, 'WIL', '10:00');
    expect(hit?.deltaMinutes).toBe(7);
  });

  it('returns nothing rather than a distant guess', () => {
    const s = groupSightings([ep('williton', '10:07:00', '10:09:00')]);
    expect(sightingFor(s, 'WIL', '14:00')).toBeNull();
    expect(sightingFor(s, 'MIN', '10:00')).toBeNull();
  });
});
