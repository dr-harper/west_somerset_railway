// How a detection and its timing are put into words.
//
// Shared so the table, the gallery caption, the drawer and the movement
// list all describe the same thing the same way — an operator comparing
// two views should never have to wonder whether "on time" means the same
// in both.

import type { Episode } from '../utils/firestore/episodes';

/** "3 minutes late" and the like, or "on time" inside a minute. */
export function delayLabel(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '—';
  if (Math.abs(minutes) < 1) return 'on time';
  return minutes > 0
    ? `${Math.round(minutes)}m late`
    : `${Math.round(-minutes)}m early`;
}

/** What the pipeline thinks a detection was. */
export function claimText(episode: Episode): string {
  const { claim } = episode;
  if (!claim) return '—';
  if (claim.kind === 'unscheduled') return 'Unscheduled';
  const timing =
    claim.delay_min === null || claim.delay_min === undefined
      ? ''
      : ` ${delayLabel(claim.delay_min)}`;
  const identity = claim.loco ?? claim.serviceType ?? '';
  return `${claim.booked_departure ?? '?'} ${identity}${timing}`.trim();
}
