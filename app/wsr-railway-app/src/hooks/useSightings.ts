import { useEffect, useState } from 'react';
import { isFirebaseConfigured } from '../firebase';
import { fetchEpisodes } from '../utils/firestore/episodes';
import { groupSightings, type Sighting } from '../services/sightings';
import { toDateKey } from '../services/calendarConfig';

/**
 * Today's camera sightings, grouped one per train per station.
 *
 * Returns an empty list rather than throwing when Firestore is not
 * configured or unreachable: the public pages must keep working on the
 * timetable alone, with the observed layer simply absent.
 */
export function useSightings(dateKey?: string): Sighting[] {
  const [sightings, setSightings] = useState<Sighting[]>([]);

  useEffect(() => {
    if (!isFirebaseConfigured) return;
    let cancelled = false;
    fetchEpisodes('all', 500)
      .then(episodes => {
        if (cancelled) return;
        // Strictly the day being viewed. An earlier version fell back to
        // the most recent day with data, which put yesterday's sightings —
        // and yesterday's photograph — against today's timetable.
        const day = dateKey ?? toDateKey(new Date());
        setSightings(groupSightings(episodes.filter(e => e.date_key === day)));
      })
      .catch(cause => console.error('Could not load sightings', cause));
    return () => {
      cancelled = true;
    };
  }, [dateKey]);

  return sightings;
}
