import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { isFirebaseConfigured } from '../../firebase';
import { fetchEpisodes, type Episode } from '../../utils/firestore/episodes';
import styles from './Admin.module.css';

interface Summary {
  total: number;
  unverified: number;
  confirmed: number;
  rejected: number;
  scheduled: number;
  unscheduled: number;
  cameras: number;
  latest: string | null;
  day: string | null;
}

function summarise(episodes: Episode[]): Summary {
  const count = (predicate: (e: Episode) => boolean) => episodes.filter(predicate).length;
  const sorted = [...episodes].sort((a, b) => b.t_enter.localeCompare(a.t_enter));
  return {
    total: episodes.length,
    unverified: count(e => e.status === 'unverified'),
    confirmed: count(e => e.status === 'confirmed'),
    rejected: count(e => e.status === 'rejected'),
    scheduled: count(e => e.claim?.kind === 'scheduled'),
    unscheduled: count(e => e.claim?.kind === 'unscheduled'),
    cameras: new Set(episodes.map(e => e.camera)).size,
    latest: sorted[0]?.t_enter ?? null,
    day: sorted[0]?.date_key ?? null,
  };
}

export const AdminOverview: React.FC = () => {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      setLoading(false);
      return;
    }
    fetchEpisodes('all', 500)
      .then(episodes => setSummary(summarise(episodes)))
      .catch(cause => {
        console.error('Failed to load episodes', cause);
        setError('Could not reach Firestore. Is the emulator running?');
      })
      .finally(() => setLoading(false));
  }, []);

  if (!isFirebaseConfigured) {
    return (
      <div className={styles.panel}>
        <h2>Not connected</h2>
        <p className={styles.muted}>
          Set <code>VITE_FIREBASE_PROJECT_ID</code> to see detections here.
          The public timetable works without it.
        </p>
      </div>
    );
  }
  if (loading) return <div className={styles.panel}>Loading…</div>;
  if (error) return <div className={styles.error}>{error}</div>;
  if (!summary || summary.total === 0) {
    return (
      <div className={styles.panel}>
        <h2>No detections yet</h2>
        <p className={styles.muted}>
          Run the watcher, then upload with{' '}
          <code>python3 upload_episodes.py --project demo-wsr</code>.
        </p>
      </div>
    );
  }

  const reviewed = summary.confirmed + summary.rejected;
  const progress = summary.total ? Math.round((reviewed / summary.total) * 100) : 0;

  return (
    <>
      <div className={styles.statRow}>
        <div className={styles.stat}>
          <span className={styles.statValue}>{summary.total}</span>
          <span className={styles.statLabel}>detections</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>{summary.scheduled}</span>
          <span className={styles.statLabel}>matched a service</span>
        </div>
        <div className={styles.stat}>
          <span className={`${styles.statValue} ${styles.accent}`}>{summary.unscheduled}</span>
          <span className={styles.statLabel}>unscheduled</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>{summary.cameras}</span>
          <span className={styles.statLabel}>cameras reporting</span>
        </div>
      </div>

      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <h2>Verification</h2>
          <Link className={styles.action} to="/admin/verify">
            {summary.unverified > 0 ? `Review ${summary.unverified}` : 'All reviewed'}
          </Link>
        </div>
        <div className={styles.bar}>
          <span className={styles.barFill} style={{ width: `${progress}%` }} />
        </div>
        <p className={styles.muted}>
          {reviewed} of {summary.total} checked by a human
          {summary.rejected > 0 && ` · ${summary.rejected} rejected as not a train`}
        </p>
      </div>

      <div className={styles.panel}>
        <h2>Latest activity</h2>
        <p className={styles.muted}>
          {summary.day && `Operating day ${summary.day}`}
          {summary.latest && ` · last detection ${summary.latest.slice(11, 16)}`}
        </p>
      </div>
    </>
  );
};
