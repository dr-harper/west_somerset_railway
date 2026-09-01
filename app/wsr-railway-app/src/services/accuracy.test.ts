import { describe, expect, it } from 'vitest';
import { ENOUGH, measureAccuracy, stillNeeded } from './accuracy';
import type { Episode } from '../utils/firestore/episodes';

function episode(status: Episode['status'], corroboration?: Episode['corroboration']): Episode {
  return {
    id: Math.random().toString(36).slice(2),
    camera: 'a', t_enter: '2026-08-31T10:00', t_exit: null,
    date_key: '2026-08-31', direction: null, zones: [], peak_conf: 0.9,
    keyframe: null, hires: null, corroboration,
    claim: { kind: 'unscheduled', booked_departure: null, serviceType: null,
             loco: null, delay_min: null, corroborating_sightings: null },
    status, verification: null,
  } as Episode;
}

describe('measureAccuracy', () => {
  it('quotes no figure from a sample too small to mean anything', () => {
    const a = measureAccuracy([episode('confirmed'), episode('confirmed')]);
    expect(a.precision).toBeNull();
    expect(a.margin).toBeNull();
    expect(stillNeeded(a)).toBe(ENOUGH - 2);
  });

  it('counts a correction as a real train, not a mistake', () => {
    // A corrected detection was a real train filed against the wrong
    // service. Only a rejection means the monitor saw something absent.
    const episodes = [
      ...Array.from({ length: 15 }, () => episode('confirmed')),
      ...Array.from({ length: 5 }, () => episode('corrected')),
    ];
    const a = measureAccuracy(episodes);
    expect(a.checked).toBe(20);
    expect(a.precision).toBe(1);
  });

  it('measures precision once there is enough to measure', () => {
    const episodes = [
      ...Array.from({ length: 18 }, () => episode('confirmed')),
      ...Array.from({ length: 2 }, () => episode('rejected')),
    ];
    const a = measureAccuracy(episodes);
    expect(a.precision).toBeCloseTo(0.9, 3);
    expect(a.margin).toBeGreaterThan(0);
    expect(stillNeeded(a)).toBe(0);
  });

  it('reports the corroboration proxy separately from verified truth', () => {
    const episodes = [
      episode('unverified', { checkable: true, corroborated: true }),
      episode('unverified', { checkable: true, corroborated: false }),
      episode('unverified', { checkable: false, reason: 'no second view' }),
    ];
    const a = measureAccuracy(episodes);
    expect(a.checkable).toBe(2);
    expect(a.corroborated).toBe(1);
    expect(a.precision).toBeNull();
  });
});
