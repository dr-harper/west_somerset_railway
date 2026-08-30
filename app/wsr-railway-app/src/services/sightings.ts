// Matching what the cameras saw to what the timetable booked.
//
// An episode records when a train came into a camera's view and when it
// left it. At a station that is an observed arrival and departure — at
// Williton this morning a train stood in the loop for thirteen minutes,
// seen independently by both cameras there.
//
// Two cameras watch several stations, so the same train produces two
// episodes at one place. They are merged, and the fact that both saw it
// is kept: independent corroboration is the strongest thing this system
// can offer, and it is worth showing.

import { CAMERAS } from './cameras';
import type { Episode } from '../utils/firestore/episodes';

/** How far from the booked time a sighting can still be that service. */
const MATCH_WINDOW_MIN = 35;

/** Sightings this far apart at one station are separate trains. */
const SAME_TRAIN_MIN = 12;

export interface Sighting {
  station: string;
  /** When the train first came into view — an observed arrival. */
  firstSeen: string;
  /** When it left view — an observed departure, where it stood. */
  lastSeen: string | null;
  /** Seconds between the two. */
  dwellSeconds: number | null;
  cameras: string[];
  episodes: Episode[];
  /** Minutes after the booked time it was first seen; negative is early. */
  deltaMinutes: number | null;
}

const STATION_OF = new Map(CAMERAS.map(c => [c.id, c.station]));

function minutesOf(iso: string): number {
  return Number(iso.slice(11, 13)) * 60 + Number(iso.slice(14, 16));
}

function bookedMinutes(hhmm: string): number {
  return Number(hhmm.slice(0, 2)) * 60 + Number(hhmm.slice(3, 5));
}

/**
 * Group a day's episodes into one sighting per train per station.
 *
 * Sorted by time, then anything at the same station within a few minutes
 * is taken to be the same train — which is what two cameras on one
 * platform produce, and also what a train that dwells and re-triggers
 * the gate produces.
 */
export function groupSightings(episodes: Episode[]): Sighting[] {
  const byStation = new Map<string, Episode[]>();
  for (const episode of episodes) {
    const station = STATION_OF.get(episode.camera);
    if (!station) continue;
    const list = byStation.get(station) ?? [];
    list.push(episode);
    byStation.set(station, list);
  }

  const sightings: Sighting[] = [];
  for (const [station, list] of byStation) {
    const sorted = [...list].sort((a, b) => a.t_enter.localeCompare(b.t_enter));
    let group: Episode[] = [];
    const flush = () => {
      if (!group.length) return;
      const firstSeen = group[0].t_enter;
      const exits = group
        .map(e => e.t_exit)
        .filter((t): t is string => Boolean(t))
        .sort();
      const lastSeen = exits.length ? exits[exits.length - 1] : null;
      sightings.push({
        station,
        firstSeen,
        lastSeen,
        dwellSeconds: lastSeen
          ? Math.round((Date.parse(lastSeen) - Date.parse(firstSeen)) / 1000)
          : null,
        cameras: [...new Set(group.map(e => e.camera))],
        episodes: group,
        deltaMinutes: null,
      });
      group = [];
    };
    for (const episode of sorted) {
      if (
        group.length &&
        minutesOf(episode.t_enter) - minutesOf(group[0].t_enter) > SAME_TRAIN_MIN
      ) {
        flush();
      }
      group.push(episode);
    }
    flush();
  }
  return sightings.sort((a, b) => a.firstSeen.localeCompare(b.firstSeen));
}

/**
 * The sighting that best explains a booked call at a station.
 *
 * Nearest in time within the window, and nothing at all when there is no
 * candidate — "not seen yet" is a real answer and a more useful one than
 * the closest thing an hour away.
 */
export function sightingFor(
  sightings: Sighting[],
  station: string,
  booked: string | null | undefined
): Sighting | null {
  if (!booked) return null;
  const target = bookedMinutes(booked);
  let best: Sighting | null = null;
  let bestGap = Infinity;
  for (const sighting of sightings) {
    if (sighting.station !== station) continue;
    const gap = minutesOf(sighting.firstSeen) - target;
    if (Math.abs(gap) > MATCH_WINDOW_MIN) continue;
    if (Math.abs(gap) < Math.abs(bestGap)) {
      best = sighting;
      bestGap = gap;
    }
  }
  return best ? { ...best, deltaMinutes: Math.round(bestGap) } : null;
}
