import { useEffect, useMemo, useState } from 'react';
import { isFirebaseConfigured } from '../../firebase';
import {
  fetchEpisodes,
  type Episode,
  type VerificationStatus,
} from '../../utils/firestore/episodes';
import styles from './Admin.module.css';

const STATION_NAMES: Record<string, string> = {
  bishops_lydeard: 'Bishops Lydeard',
  crowcombe_heathfield: 'Crowcombe',
  watchet_visitor_centre: 'Watchet',
  blue_anchor: 'Blue Anchor',
  minehead_seaward_crossing: 'Seaward Crossing',
  minehead_station: 'Minehead',
};

const FILTERS: { value: VerificationStatus | 'all'; label: string }[] = [
  { value: 'all', label: 'All' },
  { value: 'unverified', label: 'Unverified' },
  { value: 'confirmed', label: 'Confirmed' },
  { value: 'corrected', label: 'Corrected' },
  { value: 'rejected', label: 'Rejected' },
];

function claimText(episode: Episode): string {
  const { claim } = episode;
  if (!claim) return '—';
  if (claim.kind === 'unscheduled') return 'Unscheduled';
  const delay = claim.delay_min;
  const timing = delay === null || delay === undefined ? ''
    : Math.abs(delay) < 1 ? ' on time'
    : delay > 0 ? ` ${Math.round(delay)}m late` : ` ${Math.round(-delay)}m early`;
  return `${claim.booked_departure ?? '?'} ${claim.loco ?? claim.serviceType ?? ''}${timing}`;
}

export const AdminEpisodes: React.FC = () => {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [filter, setFilter] = useState<VerificationStatus | 'all'>('all');
  const [camera, setCamera] = useState('all');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Episode | null>(null);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      setLoading(false);
      return;
    }
    setLoading(true);
    fetchEpisodes('all', 500)
      .then(setEpisodes)
      .catch(cause => console.error('Failed to load episodes', cause))
      .finally(() => setLoading(false));
  }, []);

  const cameras = useMemo(
    () => Array.from(new Set(episodes.map(e => e.camera))).sort(),
    [episodes]
  );

  const shown = useMemo(() => episodes.filter(episode =>
    (filter === 'all' || episode.status === filter) &&
    (camera === 'all' || episode.camera === camera)
  ), [episodes, filter, camera]);

  if (!isFirebaseConfigured) {
    return <div className={styles.panel}>Firestore is not configured.</div>;
  }
  if (loading) return <div className={styles.panel}>Loading detections…</div>;

  return (
    <>
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
          <option value="all">All cameras</option>
          {cameras.map(name => (
            <option key={name} value={name}>{STATION_NAMES[name] ?? name}</option>
          ))}
        </select>
        <span className={styles.muted}>{shown.length} shown</span>
      </div>

      <div className={styles.panel}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Time</th><th>Where</th><th>Direction</th>
              <th>Reading</th><th>Confidence</th><th>Status</th>
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
                <td>{STATION_NAMES[episode.camera] ?? episode.camera}</td>
                <td className={styles.muted}>
                  {episode.direction === 'unclear' ? '—' : episode.direction}
                </td>
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
        {shown.length === 0 && (
          <p className={styles.muted}>Nothing matches those filters.</p>
        )}
      </div>

      {selected && (
        <div className={styles.drawer} onClick={() => setSelected(null)}>
          <div className={styles.drawerCard} onClick={event => event.stopPropagation()}>
            <div className={styles.panelHead}>
              <h2>
                {STATION_NAMES[selected.camera] ?? selected.camera}
                {' · '}{selected.t_enter.slice(11, 16)}
              </h2>
              <button className={styles.action} onClick={() => setSelected(null)}>
                Close
              </button>
            </div>
            {selected.keyframe && (
              <img
                className={styles.drawerImage}
                src={`/captures/${selected.keyframe}`}
                alt={`Detection at ${selected.camera}`}
              />
            )}
            <dl className={styles.details}>
              <dt>Reading</dt><dd>{claimText(selected)}</dd>
              <dt>Zones</dt><dd>{selected.zones?.join(', ') || '—'}</dd>
              <dt>Corroboration</dt>
              <dd>{selected.claim?.corroborating_sightings ?? 1} camera(s)</dd>
              <dt>Status</dt><dd>{selected.status}</dd>
              {selected.verification?.notes && (
                <>
                  <dt>Note</dt><dd>{selected.verification.notes}</dd>
                </>
              )}
            </dl>
          </div>
        </div>
      )}
    </>
  );
};
