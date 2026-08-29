import { useMemo } from 'react';
import { CAMERAS, cameraName } from '../../services/cameras';
import type { Episode } from '../../utils/firestore/episodes';
import styles from './DetectionRibbon.module.css';

/**
 * The operating day as a strip: cameras down the line, time across.
 *
 * A table of detections tells you what happened; it does not tell you what
 * the day looked like. Laid out this way a service pattern reads as a
 * diagonal — the same train stepping down the cameras in order — and the
 * things worth investigating become visible without being searched for: a
 * camera with an empty row, a cluster of detections at one place with no
 * matching diagonal, a long gap in the middle of the timetable.
 */

interface Props {
  episodes: Episode[];
  onSelect?: (episode: Episode) => void;
  selectedId?: string | null;
}

function minutesOf(iso: string): number {
  const time = iso.slice(11, 16);
  const [h, m] = time.split(':').map(Number);
  return h * 60 + m;
}

export const DetectionRibbon: React.FC<Props> = ({
  episodes,
  onSelect,
  selectedId,
}) => {
  const { rows, startMin, endMin, hours } = useMemo(() => {
    const times = episodes.map(e => minutesOf(e.t_enter));
    // Round out to whole hours so the axis reads as clock time rather than
    // as whenever the first train happened to be seen.
    const first = times.length ? Math.floor(Math.min(...times) / 60) * 60 : 8 * 60;
    const last = times.length ? Math.ceil(Math.max(...times) / 60) * 60 : 20 * 60;
    const span = Math.max(60, last - first);
    const present = new Set(episodes.map(e => e.camera));
    // Registry order, but only cameras that actually reported — an empty
    // row for a camera that was never switched on is noise, not signal.
    const ordered = CAMERAS.filter(c => present.has(c.id)).map(c => c.id);
    for (const id of present) if (!ordered.includes(id)) ordered.push(id);
    return {
      rows: ordered.map(id => ({
        id,
        episodes: episodes.filter(e => e.camera === id),
      })),
      startMin: first,
      endMin: first + span,
      hours: Array.from(
        { length: Math.floor(span / 60) + 1 },
        (_, i) => first + i * 60
      ),
    };
  }, [episodes]);

  if (!episodes.length) return null;

  const position = (iso: string) =>
    ((minutesOf(iso) - startMin) / (endMin - startMin)) * 100;

  return (
    <div className={styles.ribbon}>
      <div className={styles.axis}>
        <span className={styles.axisLabel} />
        <div className={styles.axisTrack}>
          {hours.map(minute => (
            <span
              key={minute}
              className={styles.tick}
              style={{ left: `${((minute - startMin) / (endMin - startMin)) * 100}%` }}
            >
              {String(Math.floor(minute / 60)).padStart(2, '0')}
            </span>
          ))}
        </div>
      </div>

      {rows.map(row => (
        <div key={row.id} className={styles.row}>
          <span className={styles.rowLabel} title={cameraName(row.id)}>
            {cameraName(row.id)}
          </span>
          <div className={styles.track}>
            {hours.map(minute => (
              <span
                key={minute}
                className={styles.gridline}
                style={{ left: `${((minute - startMin) / (endMin - startMin)) * 100}%` }}
              />
            ))}
            {row.episodes.map(episode => {
              const scheduled = episode.claim?.kind === 'scheduled';
              return (
                <button
                  key={episode.id}
                  type="button"
                  className={[
                    styles.mark,
                    scheduled ? styles.markScheduled : styles.markUnscheduled,
                    episode.status === 'rejected' ? styles.markRejected : '',
                    selectedId === episode.id ? styles.markSelected : '',
                  ].join(' ')}
                  style={{ left: `${position(episode.t_enter)}%` }}
                  onClick={() => onSelect?.(episode)}
                  title={`${cameraName(episode.camera)} ${episode.t_enter.slice(11, 16)}`}
                  aria-label={`Detection at ${cameraName(episode.camera)}, ${episode.t_enter.slice(11, 16)}`}
                />
              );
            })}
          </div>
        </div>
      ))}

      <div className={styles.key}>
        <span><i className={`${styles.dot} ${styles.markScheduled}`} /> matched to a service</span>
        <span><i className={`${styles.dot} ${styles.markUnscheduled}`} /> unscheduled</span>
        <span><i className={`${styles.dot} ${styles.markRejected}`} /> rejected</span>
      </div>
    </div>
  );
};
