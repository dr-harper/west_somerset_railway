import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { DetectionRibbon } from '../../components/Admin/DetectionRibbon';
import { EpisodeDrawer } from '../../components/Admin/EpisodeDrawer';
import { CopyId } from '../../components/Admin/CopyId';
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
  const [day, setDay] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Episode | null>(null);
  const [params, setParams] = useSearchParams();

  /**
   * The open detection, kept in the address bar.
   *
   * It used to live only in component state, so every link pointed at the
   * list and a particular detection could only be described — "the 12:43
   * Blue Anchor one" — rather than handed over. The id is already what
   * the pipeline, the capture filenames and Firestore agree on, so it is
   * the right thing to put in the URL.
   */
  const open = (episode: Episode | null) => {
    setSelected(episode);
    const next = new URLSearchParams(params);
    if (episode) next.set('episode', episode.id);
    else next.delete('episode');
    // Replaced rather than pushed: opening and closing a drawer should
    // not fill the back button with steps through the same page.
    setParams(next, { replace: true });
  };

  // A link arriving with ?episode= should open it, including on a reload,
  // which means waiting for the episodes rather than reading the param once.
  useEffect(() => {
    const wanted = params.get('episode');
    if (!wanted || !episodes.length) return;
    if (selected?.id === wanted) return;
    const found = episodes.find(e => e.id === wanted);
    if (found) setSelected(found);
  }, [episodes, params, selected]);

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

  // Every day that has data, newest first. Without this the page loaded
  // every episode ever recorded and laid two days over each other on a
  // ribbon plotted by time of day, so yesterday's 10:15 sat on top of
  // today's.
  const days = useMemo(
    () => [...new Set(episodes.map(e => e.date_key))].sort().reverse(),
    [episodes]
  );
  const showing = day || days[0] || '';
  const onDay = useMemo(
    () => episodes.filter(e => e.date_key === showing),
    [episodes, showing]
  );

  const seenCameras = useMemo(
    () => [...new Set(onDay.map(e => e.camera))],
    [onDay]
  );
  const orphans = useMemo(() => unknownCameras(seenCameras), [seenCameras]);

  const shown = useMemo(
    () =>
      onDay.filter(
        e =>
          (filter === 'all' || e.status === filter) &&
          (camera === 'all' || e.camera === camera)
      ),
    [onDay, filter, camera]
  );

  if (!isFirebaseConfigured) {
    return <div className={styles.panel}>Firestore is not configured.</div>;
  }
  if (loading) return <div className={styles.panel}>Loading detections…</div>;

  return (
    <>
      <DetectionRibbon
        episodes={shown}
        onSelect={open}
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
          value={showing}
          onChange={event => setDay(event.target.value)}
          aria-label="Day"
        >
          {days.map(d => (
            <option key={d} value={d}>{d}</option>
          ))}
        </select>
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
                onClick={() => open(episode)}
                title={episode.id}
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
              <th>ID</th>
            </tr>
          </thead>
          <tbody>
            {shown.map(episode => (
              <tr
                key={episode.id}
                className={styles.rowClickable}
                onClick={() => open(episode)}
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
                <td onClick={event => event.stopPropagation()}>
                  <CopyId id={episode.id} short />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selected && (
        <EpisodeDrawer episode={selected} onClose={() => open(null)} />
      )}
    </>
  );
};
