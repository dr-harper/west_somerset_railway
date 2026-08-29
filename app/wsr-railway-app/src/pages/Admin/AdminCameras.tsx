import { useEffect, useMemo, useState } from 'react';
import { isFirebaseConfigured } from '../../firebase';
import { fetchEpisodes, type Episode } from '../../utils/firestore/episodes';
import styles from './Admin.module.css';

// Ordered along the line, Bishops Lydeard end first
const CAMERAS = [
  { id: 'bishops_lydeard', name: 'Bishops Lydeard', mile: 0 },
  { id: 'crowcombe_heathfield', name: 'Crowcombe Heathfield', mile: 4.5 },
  { id: 'watchet_visitor_centre', name: 'Watchet', mile: 11 },
  { id: 'blue_anchor', name: 'Blue Anchor', mile: 14.5 },
  { id: 'minehead_seaward_crossing', name: 'Minehead, Seaward Crossing', mile: 18.6 },
  { id: 'minehead_station', name: 'Minehead', mile: 20 },
];

interface CameraStats {
  episodes: number;
  scheduled: number;
  rejected: number;
  latest: string | null;
  meanConfidence: number | null;
}

export const AdminCameras: React.FC = () => {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      setLoading(false);
      return;
    }
    fetchEpisodes('all', 500)
      .then(setEpisodes)
      .catch(cause => console.error('Failed to load episodes', cause))
      .finally(() => setLoading(false));
  }, []);

  const byCamera = useMemo(() => {
    const stats: Record<string, CameraStats> = {};
    for (const camera of CAMERAS) {
      const mine = episodes.filter(e => e.camera === camera.id);
      const confidences = mine
        .map(e => e.peak_conf)
        .filter((c): c is number => typeof c === 'number');
      stats[camera.id] = {
        episodes: mine.length,
        scheduled: mine.filter(e => e.claim?.kind === 'scheduled').length,
        rejected: mine.filter(e => e.status === 'rejected').length,
        latest: mine.map(e => e.t_enter).sort().at(-1) ?? null,
        meanConfidence: confidences.length
          ? confidences.reduce((a, b) => a + b, 0) / confidences.length
          : null,
      };
    }
    return stats;
  }, [episodes]);

  if (!isFirebaseConfigured) {
    return <div className={styles.panel}>Firestore is not configured.</div>;
  }
  if (loading) return <div className={styles.panel}>Loading camera activity…</div>;

  return (
    <>
      <p className={styles.muted}>
        Six public Railcam webcams, ordered along the line. Activity is what
        the detector logged, not a health check of the stream itself.
      </p>

      <div className={styles.cameraGrid}>
        {CAMERAS.map(camera => {
          const stats = byCamera[camera.id];
          const quiet = stats.episodes === 0;
          return (
            <div
              key={camera.id}
              className={`${styles.cameraCard} ${quiet ? styles.cameraQuiet : ''}`}
            >
              <div className={styles.cameraHead}>
                <span className={styles.cameraName}>{camera.name}</span>
                <span className={styles.cameraMile}>{camera.mile} mi</span>
              </div>
              <div className={styles.cameraStats}>
                <span><strong>{stats.episodes}</strong> detections</span>
                <span><strong>{stats.scheduled}</strong> matched</span>
                {stats.rejected > 0 && (
                  <span className={styles.warnText}>
                    <strong>{stats.rejected}</strong> rejected
                  </span>
                )}
              </div>
              <div className={styles.muted}>
                {stats.latest
                  ? `last seen ${stats.latest.slice(11, 16)}`
                  : 'nothing logged'}
                {stats.meanConfidence &&
                  ` · mean ${Math.round(stats.meanConfidence * 100)}% confident`}
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
};
