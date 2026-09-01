import type { Episode } from '../utils/firestore/episodes';

/**
 * How often the monitor is right, from the detections a person has checked.
 *
 * Verification existed as a page and nothing had ever been put through it,
 * so every claim about accuracy was a proxy — the share of detections a
 * second camera agreed with, which cannot be measured at all on the five
 * cameras that have no second view.
 *
 * This turns the checking into a number that grows as it is done, which is
 * the only reason anyone would keep doing it. It also refuses to state a
 * figure from too small a sample rather than flattering the operator with
 * "100% correct" after two clicks.
 */

/** Below this many checked detections, a percentage is noise. */
export const ENOUGH = 20;

export interface Accuracy {
  checked: number;
  total: number;
  confirmed: number;
  corrected: number;
  rejected: number;
  /** Share of checked detections that were real trains. Null until ENOUGH. */
  precision: number | null;
  /** Rough +/- on that share, as a percentage point spread. */
  margin: number | null;
  /** The independent proxy: detections a partner camera also saw. */
  corroborated: number;
  checkable: number;
}

export function measureAccuracy(episodes: Episode[]): Accuracy {
  const checked = episodes.filter(e => e.status !== 'unverified');
  const confirmed = checked.filter(e => e.status === 'confirmed').length;
  const corrected = checked.filter(e => e.status === 'corrected').length;
  const rejected = checked.filter(e => e.status === 'rejected').length;

  // A corrected detection was still a real train — the correction was to
  // which service or locomotive it was, not to whether it existed. Only a
  // rejection says the monitor saw something that was not there.
  const real = confirmed + corrected;
  const precision = checked.length >= ENOUGH ? real / checked.length : null;

  // Wald interval, near enough for an operator deciding whether to keep
  // checking. Not quoted at all below ENOUGH, where it would be wider than
  // the estimate.
  const margin = precision === null
    ? null
    : 1.96 * Math.sqrt((precision * (1 - precision)) / checked.length);

  const checkable = episodes.filter(e => e.corroboration?.checkable).length;
  const corroborated = episodes.filter(e => e.corroboration?.corroborated).length;

  return {
    checked: checked.length,
    total: episodes.length,
    confirmed,
    corrected,
    rejected,
    precision,
    margin,
    corroborated,
    checkable,
  };
}

/** How many more need checking before a figure can be quoted. */
export function stillNeeded(accuracy: Accuracy): number {
  return Math.max(0, ENOUGH - accuracy.checked);
}
