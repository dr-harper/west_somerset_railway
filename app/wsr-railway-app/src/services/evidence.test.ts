import { describe, expect, it } from 'vitest';
import { observations, timetableNote, describeSpan } from './evidence';
import type { Episode } from '../utils/firestore/episodes';

function episode(over: Partial<Episode> = {}): Episode {
  return {
    id: 'x', camera: 'williton', t_enter: '2026-08-31T13:27:12',
    t_exit: '2026-08-31T13:52:50', date_key: '2026-08-31',
    direction: null, zones: [], peak_conf: 0.9, keyframe: null, hires: null,
    claim: { kind: 'unscheduled', booked_departure: null, serviceType: null,
             loco: null, delay_min: null, corroborating_sightings: null },
    status: 'unverified', verification: null, ...over,
  } as Episode;
}

describe('observations', () => {
  it('states the direction even when it could not be worked out', () => {
    // The old page left the field out entirely, on 97% of detections.
    const found = observations(episode({ direction: 'unclear', path_jumps: 2 }));
    const direction = found.find(o => o.label === 'Direction');
    expect(direction?.value).toBe('could not tell');
    expect(direction?.confidence).toBe('unknown');
    expect(direction?.basis).toContain('jumped 2 times');
  });

  it('marks a worked-out direction as derived, not observed', () => {
    const found = observations(episode({ direction: 'northbound' }));
    expect(found.find(o => o.label === 'Direction')?.confidence).toBe('derived');
  });

  it('says when there is nothing to corroborate against', () => {
    const found = observations(episode({
      corroboration: { checkable: false, reason: 'no second view' },
    }));
    const second = found.find(o => o.label === 'Second camera');
    expect(second?.confidence).toBe('unknown');
    expect(second?.value).toContain('nothing to check');
  });

  it('reports more than one train held as its own observation', () => {
    const found = observations(episode({
      trains_moving: 2,
      tracks: [
        { id: 1, t_enter: '', t_exit: null, observations: 9, peak_conf: 0.9,
          moved: true, drift_x: -262, drift_y: 220, zones: 'loop' },
        { id: 2, t_enter: '', t_exit: null, observations: 4, peak_conf: 0.8,
          moved: true, drift_x: 40, drift_y: 10, zones: 'running line' },
      ],
    }));
    const held = found.find(o => o.label === 'Trains held');
    expect(held?.value).toBe('2 tracked, 2 of them moving');
    expect(held?.basis).toContain('more than one train');
  });
});

describe('timetableNote', () => {
  it('does not present an unmatched detection as a verdict on the train', () => {
    const note = timetableNote(episode());
    expect(note.value).toBe('no booked service near this time');
    expect(note.basis).toContain('not evidence the detection is wrong');
  });

  it('says what a match was made on', () => {
    const note = timetableNote(episode({
      claim: { kind: 'scheduled', booked_departure: '13:25', serviceType: 'STEAM',
               loco: null, delay_min: 2, corroborating_sightings: null },
    }));
    expect(note.value).toContain('13:25');
    expect(note.value).toContain('2 min after');
    expect(note.basis).toContain('not on anything read off the train');
  });
});

describe('describeSpan', () => {
  it('gives the length, which is how a 25-minute record gives itself away', () => {
    expect(describeSpan(episode())).toContain('25m');
  });
});

describe('a detection seen only once', () => {
  it('counts in the singular, and says so plainly', () => {
    const found = observations(episode({ observations: 1, peak_conf: 0.77 }));
    expect(found.find(o => o.label === 'Seen')?.value).toBe('1 time, best 77%');
  });
});
