import { useEffect, useMemo, useState } from 'react';
import { isFirebaseConfigured } from '../../firebase';
import { CAMERAS } from '../../services/cameras';
import { fetchEpisodes, type Episode } from '../../utils/firestore/episodes';
import styles from './Admin.module.css';

/**
 * Every camera the pipeline opens, and how ready each one is.
 *
 * Two different questions get answered here, and conflating them is what
 * made the old version misleading: whether a camera is *set up* — track
 * traced, platforms outlined, direction established — and whether it is
 * *seeing anything*. A camera can be busy and badly calibrated, or
 * perfectly annotated and pointed at a closed branch.
 */

interface CameraStats {
  episodes: number;
  scheduled: number;
  rejected: number;
  latest: string | null;
  meanConfidence: number | null;
}

const EMPTY: CameraStats = {
  episodes: 0,
  scheduled: 0,
  rejected: 0,
  latest: null,
  meanConfidence: null,
};

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

  const ready = CAMERAS.filter(c => c.annotation.ready).length;
  const oriented = CAMERAS.filter(c => c.annotation.orientationKnown).length;

  if (loading) return <div className={styles.panel}>Loading camera activity…</div>;

  return (
    <>
      <div className={styles.statRow}>
        <div className={styles.stat}>
          <span className={styles.statValue}>{CAMERAS.length}</span>
          <span className={styles.statLabel}>cameras watched</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>{ready}</span>
          <span className={styles.statLabel}>with track traced</span>
        </div>
        <div className={styles.stat}>
          <span className={`${styles.statValue} ${oriented < CAMERAS.length ? styles.accent : ''}`}>
            {oriented}
          </span>
          <span className={styles.statLabel}>direction established</span>
        </div>
      </div>

      <p className={styles.muted}>
        Ordered along the line, Bishops Lydeard end first. Setup comes from the
        hand annotations; activity is what the detector logged, not a health
        check of the stream itself.
      </p>

      <div className={styles.cameraGrid}>
        {CAMERAS.map(camera => {
          const stats = byCamera[camera.id] ?? EMPTY;
          const note = camera.annotation;
          return (
            <div
              key={camera.id}
              className={`${styles.cameraCard} ${note.ready ? '' : styles.cameraQuiet}`}
            >
              <div className={styles.cameraHead}>
                <span className={styles.cameraName}>{camera.name}</span>
                <span className={styles.cameraMile}>{camera.station ?? '—'}</span>
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
                {stats.meanConfidence
                  ? ` · mean ${Math.round(stats.meanConfidence * 100)}% confident`
                  : ''}
              </div>

              <div className={styles.setupRow}>
                <span className={note.roads ? styles.setupOn : styles.setupOff}>
                  {note.roads || 'no'} road{note.roads === 1 ? '' : 's'}
                </span>
                <span className={note.platforms ? styles.setupOn : styles.setupOff}>
                  {note.platforms || 'no'} platform{note.platforms === 1 ? '' : 's'}
                </span>
                <span className={note.blockedShare > 0 ? styles.setupOn : styles.setupOff}>
                  {Math.round(note.blockedShare * 100)}% blocked
                </span>
                <span
                  className={note.orientationKnown ? styles.setupOn : styles.setupOff}
                  title={
                    note.orientationKnown
                      ? 'Northbound established, so direction comes from drift'
                      : 'Direction falls back to the order of stations visited'
                  }
                >
                  {note.orientationKnown ? 'direction set' : 'direction unset'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
};
