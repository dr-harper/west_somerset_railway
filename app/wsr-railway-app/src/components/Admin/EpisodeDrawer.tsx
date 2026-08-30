import { useEffect } from 'react';
import { captureUrl } from '../../services/captures';
import { AnnotatedStill } from './AnnotatedStill';
import { EpisodeClip } from './EpisodeClip';
import { cameraName } from '../../services/cameras';
import { claimText } from '../../services/episodeText';
import type { Episode } from '../../utils/firestore/episodes';
import styles from '../../pages/Admin/Admin.module.css';

/**
 * One detection in full: the evidence first, the reading second.
 *
 * The hi-res still is what the operator actually judges by — traction and
 * running numbers are only legible at 1080p — so it leads, with the
 * pipeline's interpretation underneath rather than in place of it.
 */

interface Props {
  episode: Episode;
  onClose: () => void;
  footer?: React.ReactNode;
}

export const EpisodeDrawer: React.FC<Props> = ({ episode, onClose, footer }) => {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const stills = [captureUrl(episode.hires), captureUrl(episode.keyframe)];
  const duration =
    episode.t_exit
      ? Math.round(
          (Date.parse(episode.t_exit) - Date.parse(episode.t_enter)) / 1000
        )
      : null;

  return (
    <div className={styles.drawer} onClick={onClose}>
      <div
        className={styles.drawerCard}
        onClick={event => event.stopPropagation()}
        role="dialog"
        aria-label={`Detection at ${cameraName(episode.camera)}`}
      >
        <div className={styles.panelHead}>
          <h2>
            {cameraName(episode.camera)}
            {' · '}
            {episode.t_enter.slice(11, 16)}
          </h2>
          <button className={styles.action} onClick={onClose}>Close</button>
        </div>

        <AnnotatedStill
          sources={stills}
          alt={`Detection at ${cameraName(episode.camera)}`}
          boxes={episode.boxes}
        />

        <EpisodeClip
          clip={episode.clip}
          denseClip={episode.dense_clip}
          denseFrames={episode.dense_frames}
        />

        <dl className={styles.details}>
          <dt>Reading</dt><dd>{claimText(episode)}</dd>
          <dt>Direction</dt>
          <dd>{episode.direction === 'unclear' || !episode.direction
            ? 'not established'
            : episode.direction}</dd>
          <dt>Confidence</dt>
          <dd>{episode.peak_conf ? `${Math.round(episode.peak_conf * 100)}%` : '—'}</dd>
          <dt>Seen for</dt>
          <dd>{duration === null ? '—' : `${duration}s`}</dd>
          <dt>Zones</dt><dd>{episode.zones?.join(', ') || '—'}</dd>
          <dt>Corroboration</dt>
          <dd>
            {episode.claim?.corroborating_sightings ?? 1} camera
            {(episode.claim?.corroborating_sightings ?? 1) === 1 ? '' : 's'}
          </dd>
          <dt>Status</dt><dd>{episode.status}</dd>
          {episode.verification?.notes && (
            <>
              <dt>Note</dt><dd>{episode.verification.notes}</dd>
            </>
          )}
        </dl>

        {footer}
      </div>
    </div>
  );
};
