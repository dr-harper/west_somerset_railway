import { useEffect, useState } from 'react';
import { ExternalLink } from 'lucide-react';
import type { Camera } from '../../services/cameras';
import styles from './CameraLive.module.css';

/**
 * A recent frame from each camera, refreshed in place.
 *
 * The streams cannot be embedded: the YouTube embed for any of these ids
 * returns "Error 153, video player configuration error", both inside this
 * app and on its own, which is a restriction set by the rights holder
 * rather than a fault here. Railcam sell access to these cameras, so that
 * is theirs to decide, and asking is the conversation to have rather than
 * working around it.
 *
 * The pipeline is already decoding every one of these streams, so a
 * recent still costs nothing extra and answers what an operator actually
 * needs: is this camera pointing where I think, and is anything happening
 * at it. The link through to YouTube is there for when the answer is
 * "something is happening and I want to watch it".
 */

const REFRESH_MS = 30_000;

interface Props {
  camera: Camera;
  /** Written by live_snapshots.py, or by the watcher during a run. */
  liveUrl: string;
  /** The frame the annotations were drawn against, if no snapshot yet. */
  posterUrl: string;
}

export const CameraLive: React.FC<Props> = ({ camera, liveUrl, posterUrl }) => {
  const [stamp, setStamp] = useState(() => Date.now());
  const [stale, setStale] = useState(false);

  useEffect(() => {
    // Same URL each time, so the query string is the only thing making the
    // browser fetch again rather than serve the frame it already has.
    const timer = setInterval(() => setStamp(Date.now()), REFRESH_MS);
    return () => clearInterval(timer);
  }, []);

  return (
    <a
      className={styles.frame}
      href={`https://www.youtube.com/watch?v=${camera.videoId}`}
      target="_blank"
      rel="noreferrer"
      aria-label={`Watch ${camera.name} live on YouTube`}
    >
      <img
        className={styles.poster}
        src={stale ? posterUrl : `${liveUrl}?t=${stamp}`}
        alt={`Recent view from ${camera.name}`}
        onError={() => setStale(true)}
      />
      <span className={styles.play}>
        <ExternalLink size={15} aria-hidden />
        Watch on YouTube
      </span>
      <span className={styles.caption}>
        {stale ? 'reference frame' : 'updated every minute'}
      </span>
    </a>
  );
};
