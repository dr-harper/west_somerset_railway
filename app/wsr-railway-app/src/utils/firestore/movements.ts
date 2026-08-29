// Movements: the same train recognised at several cameras in turn.
//
// An episode says a train passed one camera. A movement says where it came
// from, where it got to, and how its delay ran on — which is the unit an
// operator reads. Written only by the pipeline; read-only to clients.

import {
  collection,
  getDocs,
  limit as limitTo,
  orderBy,
  query,
  where,
} from 'firebase/firestore';
import { db } from '../../firebase';

export interface MovementSighting {
  at: string;
  camera: string;
  station: string;
  conf: number | null;
}

export interface Movement {
  id: string;
  date_key: string;
  first_seen: string;
  last_seen: string;
  from: string;
  to: string;
  direction: string | null;
  sightings: number;
  miles: number;
  avg_mph: number | null;
  identity: string | null;
  observations: MovementSighting[];
  kind: 'scheduled' | 'unscheduled';
  booked_departure: string | null;
  serviceType: string | null;
  loco: string | null;
  delay_min: number | null;
  delay_start_min: number | null;
  delay_end_min: number | null;
  episode_ids: string[];
}

const COLLECTION = 'movements';

export async function fetchMovements(
  dateKey?: string,
  max = 200
): Promise<Movement[]> {
  if (!db) return [];
  const base = collection(db, COLLECTION);
  const constraints = dateKey
    ? [where('date_key', '==', dateKey), orderBy('first_seen'), limitTo(max)]
    : [orderBy('first_seen'), limitTo(max)];
  const snapshot = await getDocs(query(base, ...constraints));
  return snapshot.docs.map(
    document => ({ id: document.id, ...document.data() }) as Movement
  );
}

/**
 * Movements grouped by the train working them, newest group first.
 *
 * A loco is the natural handle for an operator checking the day: "what did
 * D7017 do" is a more useful question than "what happened at 14:20". Runs
 * with no identified traction are collected under a single unidentified
 * bucket rather than dropped.
 */
export interface TaggedTrain {
  key: string;
  loco: string | null;
  serviceType: string | null;
  movements: Movement[];
  sightings: number;
  miles: number;
}

export function groupByTrain(movements: Movement[]): TaggedTrain[] {
  const groups = new Map<string, TaggedTrain>();
  for (const movement of movements) {
    const loco = movement.loco ?? movement.identity ?? null;
    const key = loco ?? `unidentified:${movement.serviceType ?? 'unknown'}`;
    const existing = groups.get(key);
    if (existing) {
      existing.movements.push(movement);
      existing.sightings += movement.sightings;
      existing.miles += movement.miles;
    } else {
      groups.set(key, {
        key,
        loco,
        serviceType: movement.serviceType,
        movements: [movement],
        sightings: movement.sightings,
        miles: movement.miles,
      });
    }
  }
  return [...groups.values()].sort((a, b) => {
    if (Boolean(a.loco) !== Boolean(b.loco)) return a.loco ? -1 : 1;
    return b.movements.length - a.movements.length;
  });
}
