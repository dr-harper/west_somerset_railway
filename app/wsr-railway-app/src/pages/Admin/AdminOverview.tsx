import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { DetectionRibbon } from '../../components/Admin/DetectionRibbon';
import { isFirebaseConfigured } from '../../firebase';
import { CAMERAS } from '../../services/cameras';
import { fetchEpisodes, type Episode } from '../../utils/firestore/episodes';
import { fetchMovements, type Movement } from '../../utils/firestore/movements';
import styles from './Admin.module.css';

/**
 * The state of the detection run, in the order an operator needs it.
 *
 * What matters first is whether the day looks right — the ribbon answers
 * that faster than any number. Then what still needs a human: unverified
 * detections, unscheduled movements, cameras not yet set up. Counts that
 * prompt no action are kept out.
 */

export const AdminOverview: React.FC = () => {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [movements, setMovements] = useState<Movement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      setLoading(false);
      return;
    }
    Promise.all([fetchEpisodes('all', 500), fetchMovements(undefined, 300)])
      .then(([loadedEpisodes, loadedMovements]) => {
        setEpisodes(loadedEpisodes);
        setMovements(loadedMovements);
      })
      .catch(cause => {
        console.error('Failed to load detection data', cause);
        setError('Could not reach Firestore. Is the emulator running?');
      })
      .finally(() => setLoading(false));
  }, []);

  const summary = useMemo(() => {
    // The latest day only. Counting every episode ever recorded while
    // labelling the panel with the most recent date said "the day at
    // 2026-08-30" above a total that included the 29th as well.
    const sorted = [...episodes].sort((a, b) => b.t_enter.localeCompare(a.t_enter));
    const latest = sorted[0]?.date_key ?? null;
    const today = latest ? episodes.filter(e => e.date_key === latest) : episodes;
    const count = (predicate: (e: Episode) => boolean) =>
      today.filter(predicate).length;
    const reviewed = count(
      e => e.status === 'confirmed' || e.status === 'rejected' || e.status === 'corrected'
    );
    return {
      total: today.length,
      unverified: count(e => e.status === 'unverified'),
      reviewed,
      scheduled: count(e => e.claim?.kind === 'scheduled'),
      latest: sorted[0]?.t_enter ?? null,
      day: latest,
      camerasReporting: new Set(today.map(e => e.camera)).size,
      episodesToday: today,
    };
  }, [episodes]);

  const notSetUp = CAMERAS.filter(c => !c.annotation.ready);
  const unscheduled = movements.filter(m => m.kind === 'unscheduled');

  if (!isFirebaseConfigured) {
    return (
      <div className={styles.panel}>
        <h2>Not connected</h2>
        <p className={styles.muted}>
          Set <code>VITE_FIREBASE_PROJECT_ID</code> to point the control room at
          a project, or run the emulator and set{' '}
          <code>VITE_FIRESTORE_EMULATOR</code>.
        </p>
      </div>
    );
  }
  if (loading) return <div className={styles.panel}>Loading…</div>;
  if (error) return <div className={styles.error}>{error}</div>;

  if (!summary.total) {
    return (
      <div className={styles.panel}>
        <h2>No detections yet</h2>
        <p className={styles.muted}>
          Run a day, then upload it with{' '}
          <code>python3 upload_episodes.py --project demo-wsr</code>.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className={styles.statRow}>
        <div className={styles.stat}>
          <span className={styles.statValue}>{summary.total}</span>
          <span className={styles.statLabel}>detections</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>{movements.length}</span>
          <span className={styles.statLabel}>movements</span>
        </div>
        <div className={styles.stat}>
          <span className={`${styles.statValue} ${unscheduled.length ? styles.accent : ''}`}>
            {unscheduled.length}
          </span>
          <span className={styles.statLabel}>not in the timetable</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>
            {summary.camerasReporting}/{CAMERAS.length}
          </span>
          <span className={styles.statLabel}>cameras reporting</span>
        </div>
      </div>

      <div className={styles.panelHead}>
        <h2>{summary.day ? `The day at ${summary.day}` : 'The day'}</h2>
        <Link className={styles.action} to="/admin/events">Every detection</Link>
      </div>
      <DetectionRibbon episodes={summary.episodesToday} />

      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <h2>Verification</h2>
          <Link className={styles.action} to="/admin/verify">
            {summary.unverified ? `Review ${summary.unverified}` : 'All reviewed'}
          </Link>
        </div>
        <div className={styles.bar}>
          <div
            className={styles.barFill}
            style={{ width: `${(summary.reviewed / summary.total) * 100}%` }}
          />
        </div>
        <p className={styles.muted}>
          {summary.reviewed} of {summary.total} checked by hand
        </p>
      </div>

      {notSetUp.length > 0 && (
        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>Waiting on annotation</h2>
            <Link className={styles.action} to="/admin/cameras">Cameras</Link>
          </div>
          <p className={styles.muted}>
            {notSetUp.map(c => c.name).join(', ')} — no track traced, so
            detections there cannot be placed on a road.
          </p>
        </div>
      )}

      <div className={styles.panel}>
        <h2>Latest activity</h2>
        <p className={styles.muted}>
          {summary.latest
            ? `Last detection ${summary.latest.slice(11, 16)} on ${summary.day}`
            : 'Nothing logged'}
        </p>
      </div>
    </>
  );
};
