// Boundary between the app's episode types and Firestore's document API.
// Detection fields are written only by the pipeline (admin SDK); this
// module updates nothing but `status` and `verification`, which is all the
// security rules permit a client to touch.

import {
  collection,
  doc,
  getDocs,
  limit as limitTo,
  onSnapshot,
  orderBy,
  query,
  updateDoc,
  where,
  type Unsubscribe,
} from 'firebase/firestore';
import { db } from '../../firebase';

export type VerificationStatus =
  | 'unverified'
  | 'confirmed'
  | 'corrected'
  | 'rejected';

export interface EpisodeClaim {
  kind: 'scheduled' | 'unscheduled';
  booked_departure: string | null;
  serviceType: string | null;
  loco: string | null;
  delay_min: number | null;
  corroborating_sightings: number | null;
}

export interface EpisodeDetection {
  box: [number, number, number, number];
  conf: number;
  zone: string | null;
}

/**
 * Detection boxes recorded beside the still rather than drawn into it, so
 * the overlay can be lifted to read what is underneath. Absent on stills
 * captured before the pipeline stopped burning them in.
 */
export interface EpisodeBoxes {
  /** Which still the coordinates were measured against. */
  image?: string;
  width: number;
  height: number;
  detections: EpisodeDetection[];
}

export interface Episode {
  id: string;
  camera: string;
  t_enter: string;
  t_exit: string | null;
  date_key: string;
  direction: string | null;
  zones: string[];
  peak_conf: number | null;
  observations?: number | null;
  drift_px?: number[] | null;
  /** One entry per train the tracker held during this record. */
  tracks?: {
    id: number; t_enter: string; t_exit: string | null;
    observations: number; peak_conf: number; moved: boolean;
    drift_x: number; drift_y: number; zones: string;
  }[] | null;
  trains_moving?: number | null;
  /** A jumped path is why a direction comes back unclear. */
  path_jumps?: number | null;
  most_in_frame?: number | null;
  /** What a classifier read off the train: traction, class, running number. */
  reading?: {
    traction: string | null;
    train_class: string | null;
    number: string | null;
    livery: string | null;
    confidence: number | null;
    notes: string | null;
  } | null;
  keyframe: string | null;
  hires: string | null;
  boxes?: EpisodeBoxes | null;
  /** Low-rate clip for review — a frame every few seconds. */
  clip?: string | null;
  /** Stream-rate clip of the passage, where the watcher captured one. */
  dense_clip?: string | null;
  dense_frames?: number | null;
  /** Whether the second camera on the same rails saw this too. */
  corroboration?: {
    checkable: boolean;
    reason?: string;
    corroborated?: boolean;
    partner?: string;
    partner_episode?: string | null;
  } | null;
  claim: EpisodeClaim;
  status: VerificationStatus;
  verification: {
    at: string;
    correctedService?: string;
    correctedLoco?: string;
    notes?: string;
  } | null;
}

const COLLECTION = 'episodes';

function toEpisode(id: string, data: Record<string, unknown>): Episode {
  return { id, ...(data as Omit<Episode, 'id'>) };
}

export async function fetchEpisodes(
  status: VerificationStatus | 'all' = 'unverified',
  max = 100
): Promise<Episode[]> {
  if (!db) return [];
  const base = collection(db, COLLECTION);
  const constraints = status === 'all'
    ? [orderBy('t_enter', 'desc'), limitTo(max)]
    : [where('status', '==', status), orderBy('t_enter', 'desc'), limitTo(max)];
  const snapshot = await getDocs(query(base, ...constraints));
  return snapshot.docs.map(d => toEpisode(d.id, d.data()));
}

export function watchEpisodes(
  status: VerificationStatus | 'all',
  callback: (episodes: Episode[]) => void,
  max = 100
): Unsubscribe {
  if (!db) return () => undefined;
  const base = collection(db, COLLECTION);
  const constraints = status === 'all'
    ? [orderBy('t_enter', 'desc'), limitTo(max)]
    : [where('status', '==', status), orderBy('t_enter', 'desc'), limitTo(max)];
  return onSnapshot(query(base, ...constraints), snapshot => {
    callback(snapshot.docs.map(d => toEpisode(d.id, d.data())));
  });
}

export async function verifyEpisode(
  id: string,
  status: Exclude<VerificationStatus, 'unverified'>,
  details: {
    correctedService?: string;
    correctedLoco?: string;
    notes?: string;
    /** Which way the verifier saw it go, from watching the clip. */
    observedDirection?: string;
    /** Whether it came to a stand, which no still can show. */
    observedStopped?: boolean;
  } = {}
): Promise<void> {
  if (!db) throw new Error('Verification needs Firestore to be configured');
  await updateDoc(doc(db, COLLECTION, id), {
    status,
    verification: { at: new Date().toISOString(), ...details },
  });
}

export async function verificationCounts(): Promise<Record<string, number>> {
  const episodes = await fetchEpisodes('all', 500);
  return episodes.reduce<Record<string, number>>((counts, episode) => {
    counts[episode.status] = (counts[episode.status] ?? 0) + 1;
    return counts;
  }, {});
}
