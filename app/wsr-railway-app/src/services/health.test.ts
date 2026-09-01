import { describe, expect, it } from 'vitest';
import { assessHealth, corroborationRate, episodesOn } from './health';
import type { Episode } from '../utils/firestore/episodes';
import type { Camera } from './cameras';

/**
 * Each case here is a failure that actually happened and was noticed only
 * because someone asked. The point of these checks is that nobody has to.
 */

function episode(over: Partial<Episode> & { camera: string; t_enter: string }): Episode {
  return {
    id: `${over.t_enter}_${over.camera}`,
    date_key: over.t_enter.slice(0, 10),
    t_exit: null,
    direction: null,
    zones: [],
    peak_conf: 0.9,
    keyframe: null,
    hires: null,
    claim: { kind: 'unscheduled', booked_departure: null, serviceType: null,
            loco: null, delay_min: null, corroborating_sightings: null },
    status: 'unverified',
    verification: null,
    ...over,
  } as Episode;
}

function camera(id: string, ready = true): Camera {
  return {
    id,
    name: id,
    station: null,
    stationName: null,
    annotation: { roads: 2, platforms: 1, occluders: 0, blockedShare: 0.5,
                  orientationKnown: true, ready },
  } as Camera;
}

const CAMERAS = [camera('a'), camera('b'), camera('c')];
const at = (time: string) => new Date(`2026-08-31T${time}:00`);

describe('assessHealth', () => {
  it('raises a critical alert when the day never started', () => {
    const alerts = assessHealth({ episodes: [], cameras: CAMERAS, now: at('09:30') });
    const alert = alerts.find(a => a.id === 'no-start');
    expect(alert?.severity).toBe('critical');
  });

  it('stays quiet in the grace period just after the start', () => {
    const alerts = assessHealth({ episodes: [], cameras: CAMERAS, now: at('08:10') });
    expect(alerts.find(a => a.id === 'no-start')).toBeUndefined();
  });

  it('stays quiet outside running hours', () => {
    const alerts = assessHealth({ episodes: [], cameras: CAMERAS, now: at('23:00') });
    expect(alerts.find(a => a.id === 'no-start')).toBeUndefined();
  });

  it('accuses capture only when the pipeline has reported in since', () => {
    const episodes = [episode({ camera: 'a', t_enter: '2026-08-31T09:00' })];
    const alerts = assessHealth({
      episodes, cameras: CAMERAS, now: at('11:00'),
      pipeline: { uploaded_at: '2026-08-31T10:55:00', latest_episode: '2026-08-31T09:00' },
    });
    const alert = alerts.find(a => a.id === 'gone-quiet');
    expect(alert?.severity).toBe('critical');
    expect(alert?.title).toContain('120 minutes');
  });

  it('blames the upload, not capture, when the pipeline is also behind', () => {
    // This fired for real: it said capture had stopped while the watcher was
    // running and writing to disk. Only the upload was late.
    const episodes = [episode({ camera: 'a', t_enter: '2026-08-31T09:00' })];
    const alerts = assessHealth({
      episodes, cameras: CAMERAS, now: at('11:00'),
      pipeline: { uploaded_at: '2026-08-31T09:05:00', latest_episode: '2026-08-31T09:00' },
    });
    expect(alerts.find(a => a.id === 'gone-quiet')).toBeUndefined();
    const stale = alerts.find(a => a.id === 'stale-upload');
    expect(stale?.severity).toBe('warning');
  });

  it('will not guess which it is when the pipeline has never reported', () => {
    const episodes = [episode({ camera: 'a', t_enter: '2026-08-31T09:00' })];
    const alerts = assessHealth({ episodes, cameras: CAMERAS, now: at('11:00') });
    expect(alerts.find(a => a.id === 'gone-quiet')).toBeUndefined();
    expect(alerts.find(a => a.id === 'stale-upload')?.detail)
      .toContain('never reported in');
  });

  it('does not call a normal gap a failure', () => {
    const episodes = [episode({ camera: 'a', t_enter: '2026-08-31T10:45' })];
    const alerts = assessHealth({ episodes, cameras: CAMERAS, now: at('11:00') });
    expect(alerts.find(a => a.id === 'gone-quiet')).toBeUndefined();
  });

  it('names a camera that has seen nothing while others report', () => {
    // Crowcombe was blind for a whole day and the control room said nothing.
    const episodes = [
      episode({ camera: 'a', t_enter: '2026-08-31T10:00' }),
      episode({ camera: 'b', t_enter: '2026-08-31T10:30' }),
    ];
    const alerts = assessHealth({ episodes, cameras: CAMERAS, now: at('11:00') });
    const alert = alerts.find(a => a.id === 'silent-cameras');
    expect(alert?.detail).toContain('c');
    expect(alert?.severity).toBe('warning');
  });

  it('escalates when most of the line is silent', () => {
    const episodes = [episode({ camera: 'a', t_enter: '2026-08-31T10:50' })];
    const alerts = assessHealth({ episodes, cameras: CAMERAS, now: at('11:00') });
    expect(alerts.find(a => a.id === 'silent-cameras')?.severity).toBe('critical');
  });

  it('flags a camera its partner keeps failing to confirm', () => {
    // The Williton roof: one of a pair seeing trains the other cannot.
    const episodes = [
      ...Array.from({ length: 8 }, (_, i) => episode({
        camera: 'a', t_enter: `2026-08-31T10:0${i}`,
        corroboration: { checkable: true, corroborated: i < 2, partner: 'b' },
      })),
      ...Array.from({ length: 8 }, (_, i) => episode({
        camera: 'b', t_enter: `2026-08-31T10:1${i}`,
        corroboration: { checkable: true, corroborated: i < 7, partner: 'a' },
      })),
    ];
    const alerts = assessHealth({ episodes, cameras: CAMERAS, now: at('11:00') });
    const alert = alerts.find(a => a.id === 'disagrees-a');
    expect(alert).toBeDefined();
    expect(alert?.detail).toContain('25%');
    expect(alerts.find(a => a.id === 'disagrees-b')).toBeUndefined();
  });

  it('says when nothing has ever been verified', () => {
    const episodes = [episode({ camera: 'a', t_enter: '2026-08-31T10:50' })];
    const alerts = assessHealth({ episodes, cameras: CAMERAS, now: at('11:00') });
    expect(alerts.find(a => a.id === 'never-verified')).toBeDefined();
  });

  it('stops saying it once verification has begun', () => {
    const episodes = [
      episode({ camera: 'a', t_enter: '2026-08-31T10:50', status: 'confirmed' }),
    ];
    const alerts = assessHealth({ episodes, cameras: CAMERAS, now: at('11:00') });
    expect(alerts.find(a => a.id === 'never-verified')).toBeUndefined();
  });

  it('puts the most serious first', () => {
    const alerts = assessHealth({
      episodes: [], cameras: [...CAMERAS, camera('d', false)], now: at('09:30'),
    });
    expect(alerts[0].severity).toBe('critical');
    expect(alerts[alerts.length - 1].severity).toBe('info');
  });
});

describe('corroborationRate', () => {
  it('will not judge a camera on too few detections', () => {
    const episodes = [episode({
      camera: 'a', t_enter: '2026-08-31T10:00',
      corroboration: { checkable: true, corroborated: false, partner: 'b' },
    })];
    expect(corroborationRate(episodes, 'a')).toBeNull();
  });
});

describe('episodesOn', () => {
  it('keeps only the day in question', () => {
    const episodes = [
      episode({ camera: 'a', t_enter: '2026-08-30T10:00' }),
      episode({ camera: 'a', t_enter: '2026-08-31T10:00' }),
    ];
    expect(episodesOn(episodes, at('11:00'))).toHaveLength(1);
  });
});

describe('a heartbeat that is present but unusable', () => {
  it('is treated as no heartbeat at all, never as NaN', () => {
    // The status document read back empty because the security rules did
    // not admit it, and an empty object is still truthy.
    const episodes = [episode({ camera: 'a', t_enter: '2026-08-31T09:00' })];
    const alerts = assessHealth({
      episodes, cameras: CAMERAS, now: at('11:00'),
      pipeline: {} as never,
    });
    const stale = alerts.find(a => a.id === 'stale-upload');
    expect(stale?.detail).toContain('never reported in');
    expect(stale?.detail).not.toContain('NaN');
  });
});
