import type { Episode } from '../utils/firestore/episodes';
import { cameraName } from './cameras';

/**
 * What was actually observed, said plainly, before anything is concluded.
 *
 * Verification used to open with "We think this is — Not in the timetable,
 * an unscheduled working" and three buttons. That asks someone to rule on a
 * conclusion they have no way to check, from a page that showed a still, a
 * time, and nothing else. Worse, it hid the direction whenever it was
 * unclear, which is 97% of detections and precisely the thing worth knowing.
 *
 * So the evidence comes first and the inference is kept separate and
 * labelled. Where the pipeline could not tell, it says so rather than
 * leaving the line out — an absent field reads as "fine", and it is not.
 */

export type Confidence = 'observed' | 'derived' | 'unknown';

export interface Observation {
  label: string;
  value: string;
  /** Whether this was seen, worked out, or could not be established. */
  confidence: Confidence;
  /** How it was arrived at, where that is not obvious. */
  basis?: string;
}

function seconds(episode: Episode): number | null {
  if (!episode.t_exit) return null;
  return (new Date(episode.t_exit).getTime() - new Date(episode.t_enter).getTime()) / 1000;
}

export function describeSpan(episode: Episode): string {
  const length = seconds(episode);
  const from = episode.t_enter.slice(11, 19);
  if (length === null) return `from ${from}, still open`;
  const to = episode.t_exit!.slice(11, 19);
  const minutes = Math.floor(length / 60);
  const rest = Math.round(length % 60);
  const span = minutes ? `${minutes}m ${rest}s` : `${rest}s`;
  return `${from} to ${to} — ${span}`;
}

/** Everything the detector and tracker recorded, as evidence to weigh. */
export function observations(episode: Episode): Observation[] {
  const out: Observation[] = [];

  out.push({
    label: 'Where',
    value: cameraName(episode.camera),
    confidence: 'observed',
    basis: episode.zones?.length ? `on the ${episode.zones.join(', ')}` : undefined,
  });

  out.push({
    label: 'When',
    value: describeSpan(episode),
    confidence: 'observed',
  });

  if (episode.observations != null) {
    out.push({
      label: 'Seen',
      value: `${episode.observations} time${episode.observations === 1 ? '' : 's'}`
        + (episode.peak_conf ? `, best ${Math.round(episode.peak_conf * 100)}%` : ''),
      confidence: 'observed',
      basis: 'each one a separate frame the detector found a train in',
    });
  }

  // Direction is stated even — especially — when it could not be worked out.
  const jumps = episode.path_jumps ?? 0;
  if (episode.direction && episode.direction !== 'unclear') {
    out.push({
      label: 'Direction',
      value: episode.direction,
      confidence: 'derived',
      basis: 'from how the detection drifted across the frame',
    });
  } else {
    out.push({
      label: 'Direction',
      value: 'could not tell',
      confidence: 'unknown',
      basis: jumps
        ? `the tracked path jumped ${jumps} time${jumps === 1 ? '' : 's'}, `
          + 'which usually means two trains were taken for one'
        : 'the detection did not drift far enough one way to be sure',
    });
  }

  const tracks = episode.tracks ?? [];
  if (tracks.length) {
    const moved = episode.trains_moving ?? tracks.filter(t => t.moved).length;
    out.push({
      label: 'Trains held',
      value: `${tracks.length} tracked, ${moved} of them moving`,
      confidence: 'observed',
      basis: tracks.length > 1
        ? 'more than one train was in view during this record'
        : undefined,
    });
  }

  const reading = episode.reading;
  if (reading && (reading.traction || reading.number)) {
    const bits = [reading.number, reading.train_class, reading.traction]
      .filter(Boolean);
    out.push({
      label: 'Read off it',
      value: bits.length ? bits.join(' — ') : 'nothing legible',
      confidence: 'derived',
      basis: [reading.livery, 'read from a still by a classifier, so this is '
        + 'the line most worth checking against the picture'].filter(Boolean).join(' · '),
    });
  } else {
    out.push({
      label: 'Read off it',
      value: 'nothing read',
      confidence: 'unknown',
      basis: reading
        ? 'the classifier could not tell what this was'
        : 'no classifier has looked at this one yet',
    });
  }

  const corroboration = episode.corroboration;
  if (corroboration?.checkable) {
    out.push({
      label: 'Second camera',
      value: corroboration.corroborated
        ? `confirmed by ${cameraName(corroboration.partner ?? '')}`
        : `${cameraName(corroboration.partner ?? '')} saw nothing at the time`,
      confidence: 'observed',
      basis: corroboration.corroborated
        ? 'two cameras on the same rails agreed'
        : 'a detection its pair cannot see is often scenery',
    });
  } else {
    out.push({
      label: 'Second camera',
      value: 'nothing to check against',
      confidence: 'unknown',
      basis: corroboration?.reason ?? 'this camera has no second view of the same rails',
    });
  }

  return out;
}

/**
 * The timetable comparison, phrased as what was compared rather than as a
 * verdict on the train.
 */
export function timetableNote(episode: Episode): Observation {
  const { claim } = episode;
  if (claim?.kind === 'scheduled') {
    const bits = [`the ${claim.booked_departure}`];
    if (claim.loco) bits.push(claim.loco);
    else if (claim.serviceType) bits.push(claim.serviceType.toLowerCase());
    const late = claim.delay_min;
    const timing = late == null ? ''
      : late > 0 ? `, ${late} min after its booked time`
      : late < 0 ? `, ${-late} min before it`
      : ', on time';
    return {
      label: 'Against the timetable',
      value: `matches ${bits.join(' — ')}${timing}`,
      confidence: 'derived',
      basis: 'matched on time and direction, not on anything read off the train',
    };
  }
  return {
    label: 'Against the timetable',
    value: 'no booked service near this time',
    confidence: 'derived',
    basis: 'which may mean a special, a light engine, shunting — or that the '
      + 'match failed. It is not evidence the detection is wrong.',
  };
}
