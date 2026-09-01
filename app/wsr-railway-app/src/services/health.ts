import type { Episode } from '../utils/firestore/episodes';
import type { Camera } from './cameras';
import { cameraName } from './cameras';

/**
 * Whether the monitor is actually working, said out loud.
 *
 * Every check here exists because the failure it looks for has already
 * happened and nobody noticed. Two mornings were lost to a scheduled run
 * that never started — once to a log path that stopped the job spawning,
 * once to a missing PATH that made every stream return "not available" —
 * and on both days the control room looked exactly as it does on a good
 * one. Crowcombe was blind for a whole day and said nothing. The network
 * changed and the page pointed at a machine that no longer existed,
 * rendering perfectly with no data in it.
 *
 * Silence is the normal failure of this system, so the product has to
 * treat an absence of detections as a finding rather than as a quiet day.
 */

export type Severity = 'critical' | 'warning' | 'info';

export interface Alert {
  id: string;
  severity: Severity;
  title: string;
  detail: string;
  /** Where an operator would go to act on it. */
  to?: string;
}

/** When the pipeline last pushed to the control room, and what it had. */
export interface Pipeline {
  uploaded_at: string;
  latest_episode: string | null;
}

export interface HealthInput {
  episodes: Episode[];
  cameras: Camera[];
  now: Date;
  /** Absent means the pipeline has never reported in. */
  pipeline?: Pipeline | null;
  /** When the watcher is scheduled to start, local time. */
  startHour?: number;
  /** When it is expected to stop. */
  endHour?: number;
}

/** Minutes of no detection, during running hours, before it is suspicious. */
const QUIET_MINUTES = 45;
/** Grace after the scheduled start before a silent morning is an alarm. */
const START_GRACE_MINUTES = 20;
/**
 * A camera confirmed by its partner far less often than that partner is
 * confirmed in return is seeing things the other cannot. Williton 2 sat at
 * roughly a third while its pair sat near two thirds, which was the roof.
 */
const DISAGREEMENT_GAP = 0.3;

function dayKey(when: Date): string {
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${when.getFullYear()}-${pad(when.getMonth() + 1)}-${pad(when.getDate())}`;
}

function minutesBetween(a: Date, b: Date): number {
  return Math.abs(a.getTime() - b.getTime()) / 60000;
}

/** Detections from the day `now` falls in. */
export function episodesOn(episodes: Episode[], now: Date): Episode[] {
  const key = dayKey(now);
  return episodes.filter(e => (e.date_key ?? e.t_enter.slice(0, 10)) === key);
}

function latest(episodes: Episode[]): Episode | null {
  return episodes.reduce<Episode | null>(
    (newest, e) => (!newest || e.t_enter > newest.t_enter ? e : newest), null);
}

export function corroborationRate(episodes: Episode[], camera: string): number | null {
  const mine = episodes.filter(
    e => e.camera === camera && e.corroboration?.checkable);
  if (mine.length < 4) return null;   // too few to say anything
  return mine.filter(e => e.corroboration?.corroborated).length / mine.length;
}

export function assessHealth(input: HealthInput): Alert[] {
  const { episodes, cameras, now, pipeline, startHour = 8, endHour = 19 } = input;
  const today = episodesOn(episodes, now);
  const hour = now.getHours() + now.getMinutes() / 60;
  const running = hour >= startHour && hour <= endHour;
  const sinceStart = (hour - startHour) * 60;
  const alerts: Alert[] = [];

  // 1. The scheduled run never started. Both lost mornings looked like this.
  if (running && sinceStart > START_GRACE_MINUTES && today.length === 0) {
    alerts.push({
      id: 'no-start',
      severity: 'critical',
      title: 'Nothing captured today',
      detail: `The watcher was due to start at ${String(startHour).padStart(2, '0')}:00 and `
        + `nothing has been recorded in the ${Math.round(sinceStart)} minutes since. `
        + 'On two occasions this meant the scheduled job failed silently.',
      to: '/admin/cameras',
    });
  }

  // 2. Nothing recent. Which of two very different things that means depends
  //    on whether the pipeline has reported in since — a stale upload looks
  //    exactly like a stopped watcher from here, and saying the wrong one is
  //    worse than saying neither. This alert claimed capture had failed while
  //    the watcher was running and writing to disk.
  const newest = latest(today);
  if (running && newest && today.length > 0) {
    const quiet = minutesBetween(now, new Date(newest.t_enter));
    // A heartbeat that is present but unusable counts as absent. The
    // status document read back empty once — the security rules did not
    // admit it — and an object without a timestamp is still truthy, so the
    // panel offered an operator "the pipeline last reported NaN minutes ago".
    const reportedAt = pipeline ? new Date(pipeline.uploaded_at) : null;
    const uploadAge = reportedAt && !Number.isNaN(reportedAt.getTime())
      ? minutesBetween(now, reportedAt)
      : null;
    const uploadIsFresh = uploadAge !== null && uploadAge < QUIET_MINUTES;

    if (quiet > QUIET_MINUTES && uploadIsFresh) {
      alerts.push({
        id: 'gone-quiet',
        severity: 'critical',
        title: `No detections for ${Math.round(quiet)} minutes`,
        detail: `The last was ${newest.t_enter.slice(11, 16)} at ${cameraName(newest.camera)}, `
          + `and the pipeline reported in ${Math.round(uploadAge!)} minutes ago with `
          + 'nothing newer. Capture has stopped rather than the line being quiet.',
        to: '/admin/events',
      });
    } else if (quiet > QUIET_MINUTES) {
      alerts.push({
        id: 'stale-upload',
        severity: 'warning',
        title: `This page is ${Math.round(quiet)} minutes behind`,
        detail: uploadAge !== null
          ? `The pipeline last reported ${Math.round(uploadAge)} minutes ago. `
            + 'Detections may be happening and not reaching the control room; '
            + 'nothing here can tell you which until it uploads again.'
          : 'The pipeline has never reported in, so there is no way to tell a '
            + 'quiet line from an upload that is not running.',
        to: '/admin/events',
      });
    }
  }

  // 3. A camera that has seen nothing while others are reporting.
  if (today.length > 0) {
    const reporting = new Set(today.map(e => e.camera));
    const silent = cameras.filter(c => c.annotation.ready && !reporting.has(c.id));
    if (silent.length) {
      alerts.push({
        id: 'silent-cameras',
        severity: silent.length >= cameras.length / 2 ? 'critical' : 'warning',
        title: silent.length === 1
          ? `${cameraName(silent[0].id)} has seen nothing today`
          : `${silent.length} cameras have seen nothing today`,
        detail: `${silent.map(c => cameraName(c.id)).join(', ')} reported no `
          + 'detections while other cameras did. A stream that is down at source '
          + 'looks identical to a quiet stretch of railway.',
        to: '/admin/cameras',
      });
    }
  }

  // 4. A camera whose partner keeps disagreeing with it — the roof problem.
  for (const camera of cameras) {
    const mine = corroborationRate(today, camera.id);
    if (mine === null) continue;
    const partnerId = today.find(
      e => e.camera === camera.id && e.corroboration?.partner)?.corroboration?.partner;
    if (!partnerId) continue;
    const theirs = corroborationRate(today, partnerId);
    if (theirs === null) continue;
    if (theirs - mine > DISAGREEMENT_GAP) {
      alerts.push({
        id: `disagrees-${camera.id}`,
        severity: 'warning',
        title: `${cameraName(camera.id)} is often alone`,
        detail: `${Math.round(mine * 100)}% of its detections were confirmed by `
          + `${cameraName(partnerId)}, against ${Math.round(theirs * 100)}% the other `
          + 'way. A camera seeing trains its pair cannot is usually detecting scenery.',
        to: `/admin/events`,
      });
    }
  }

  // 5. A camera that cannot place a detection on a road.
  const unready = cameras.filter(c => !c.annotation.ready);
  if (unready.length) {
    alerts.push({
      id: 'unannotated',
      severity: 'info',
      title: unready.length === 1
        ? `${cameraName(unready[0].id)} has no track traced`
        : `${unready.length} cameras have no track traced`,
      detail: `${unready.map(c => cameraName(c.id)).join(', ')} cannot place a `
        + 'detection on a road, so nothing there can be corroborated or given a direction.',
      to: '/admin/annotate',
    });
  }

  // 6. Nothing has ever been checked by a person.
  const reviewed = episodes.filter(e => e.status !== 'unverified').length;
  if (episodes.length > 0 && reviewed === 0) {
    alerts.push({
      id: 'never-verified',
      severity: 'warning',
      title: 'No detection has been verified',
      detail: `${episodes.length} detections recorded and none checked by hand. `
        + 'Until some are, there is no measure of how often the monitor is right '
        + 'and no way to notice it getting worse.',
      to: '/admin/verify',
    });
  }

  const order: Record<Severity, number> = { critical: 0, warning: 1, info: 2 };
  return alerts.sort((a, b) => order[a.severity] - order[b.severity]);
}
