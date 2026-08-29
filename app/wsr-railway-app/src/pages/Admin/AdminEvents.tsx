import { useEffect, useMemo, useState } from 'react';
import { DetectionRibbon } from '../../components/Admin/DetectionRibbon';
import { EpisodeDrawer } from '../../components/Admin/EpisodeDrawer';
import { isFirebaseConfigured } from '../../firebase';
import { captureUrl } from '../../services/captures';
import { claimText } from '../../services/episodeText';
import { CAMERAS, cameraName, unknownCameras } from '../../services/cameras';
import {
  fetchEpisodes,
  type Episode,
  type VerificationStatus,
} from '../../utils/firestore/episodes';
import styles from './Admin.module.css';

const FILTERS: { value: VerificationStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'unverified', label: 'Unverified' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'corrected', label: 'Corrected' },
  { value: 'rejected', label: 'Rejected' },
];

export const AdminEvents: React.FC = () => {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [filter, setFilter] = useState<VerificationStatus | 'all'>('all');
  const [camera, setCamera] = useState('all');
  const [view, setView] = useState<'stills' | 'table'>('stills');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Episode | null>(null);

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

  const seenCameras = useMemo(
    () => [...new Set(episodes.map(e => e.camera))],
    [episodes]
  );
  const orphans = useMemo(() => unknownCameras(seenCameras), [seenCameras]);

  const shown = useMemo(
    () =>
      episodes.filter(
        e =>
          (filter === 'all' || e.status === filter) &&
          (camera === 'all' || e.camera === camera)
      ),
    [episodes, filter, camera]
  );

  if (!isFirebaseConfigured) {
    return <div className={styles.panel}>Firestore is not configured.</div>;
  }
  if (loading) return <div className={styles.panel}>Loading detections…</div>;

  return (
    <>
      <DetectionRibbon
        episodes={shown}
        onSelect={setSelected}
        selectedId={selected?.id ?? null}
      />

      <div className={styles.filterRow}>
        <div className={styles.chips}>
          {FILTERS.map(option => (
            <button
              key={option.value}
              className={`${styles.chip} ${filter === option.value ? styles.chipOn : ''}`}
              onClick={() => setFilter(option.value)}
            >
              {option.label}
            </button>
          ))}
        </div>
        <select
          className={styles.select}
          value={camera}
          onChange={event => setCamera(event.target.value)}
        >
          <option value="all">Every camera</option>
          {CAMERAS.filter(c => seenCameras.includes(c.id)).map(c => (
            <option key={c.id} value={c.id}>{c.name}</option>
          ))}
          {orphans.map(id => (
            <option key={id} value={id}>{id} (not in registry)</option>
          ))}
        </select>
        <div className={styles.chips}>
          <button
            className={`${styles.chip} ${view === 'stills' ? styles.chipOn : ''}`}
            onClick={() => setView('stills')}
          >
            Stills
          </button>
          <button
            className={`${styles.chip} ${view === 'table' ? styles.chipOn : ''}`}
            onClick={() => setView('table')}
          >
            Table
          </button>
        </div>
        <span className={styles.muted}>{shown.length} shown</span>
      </div>

      {orphans.length > 0 && (
        <p className={styles.warnText}>
          {orphans.length} camera{orphans.length > 1 ? 's have' : ' has'} reported
          detections but {orphans.length > 1 ? 'are' : 'is'} missing from the
          registry ({orphans.join(', ')}). Re-run{' '}
          <code>python3 camera_registry.py --write</code>.
        </p>
      )}

      {shown.length === 0 && (
        <div className={styles.panel}>Nothing matches those filters.</div>
      )}

      {view === 'stills' && shown.length > 0 && (
        <div className={styles.stillGrid}>
          {shown.map(episode => {
            const src = captureUrl(episode.keyframe);
            return (
              <button
                key={episode.id}
                className={styles.still}
                onClick={() => setSelected(episode)}
              >
                {src ? (
                  <img src={src} alt="" loading="lazy" className={styles.stillImage} />
                ) : (
                  <span className={styles.stillMissing}>no still</span>
                )}
                <span className={styles.stillMeta}>
                  <strong>{episode.t_enter.slice(11, 16)}</strong>
                  <span>{cameraName(episode.camera)}</span>
                </span>
                <span
                  className={`${styles.stillTag} ${
                    episode.claim?.kind === 'scheduled' ? styles.tagScheduled : styles.tagUnscheduled
                  }`}
                >
                  {episode.claim?.kind === 'scheduled'
                    ? (episode.claim.loco ?? episode.claim.serviceType ?? 'service')
                    : 'unscheduled'}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {view === 'table' && shown.length > 0 && (
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Time</th>
              <th>Where</th>
              <th>Direction</th>
              <th>Reading</th>
              <th>Confidence</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(episode => (
              <tr
                key={episode.id}
                className={styles.rowClickable}
                onClick={() => setSelected(episode)}
              >
                <td className={styles.mono}>{episode.t_enter.slice(11, 16)}</td>
                <td>{cameraName(episode.camera)}</td>
                <td>{episode.direction === 'unclear' ? '—' : episode.direction}</td>
                <td>{claimText(episode)}</td>
                <td className={styles.mono}>
                  {episode.peak_conf ? `${Math.round(episode.peak_conf * 100)}%` : '—'}
                </td>
                <td>
                  <span className={`${styles.badge} ${styles[episode.status] ?? ''}`}>
                    {episode.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selected && (
        <EpisodeDrawer episode={selected} onClose={() => setSelected(null)} />
      )}
    </>
  );
};
