import { useState } from 'react';
import { Film, Gauge } from 'lucide-react';
import { captureNote, useCapture } from '../../services/captures';
import styles from './EpisodeClip.module.css';

/**
 * The recorded passage, so a detection can be judged by watching it.
 *
 * Two clips exist and they are not interchangeable. The review clip is
 * whatever the watcher sampled while working — in practice about one
 * frame every five seconds, which is enough to see that something went
 * past but not to tell a locomotive from the third coach. The dense clip
 * is the stream's own 25fps for the length of the passage, and it is the
 * one worth watching; it only exists for episodes recorded after the
 * watcher started keeping them.
 */

interface Props {
  clip?: string | null;
  denseClip?: string | null;
  denseFrames?: number | null;
}

export const EpisodeClip: React.FC<Props> = ({ clip, denseClip, denseFrames }) => {
  const available = [
    denseClip ? { key: 'dense', name: denseClip, label: 'Full speed' } : null,
    clip ? { key: 'review', name: clip, label: 'Sampled' } : null,
  ].filter(Boolean) as { key: string; name: string; label: string }[];

  const [chosen, setChosen] = useState(available[0]?.key);
  const showing = available.find(option => option.key === chosen) ?? available[0];

  // Resolved before the early return below, because a hook may not sit
  // behind a branch. An absent name simply resolves to nothing.
  const { url: source, state } = useCapture(showing?.name);

  if (!showing) {
    return (
      <p className={styles.none}>
        <Film size={14} aria-hidden />
        No clip was recorded for this detection
      </p>
    );
  }

  if (state === 'forbidden' || state === 'missing') {
    return (
      <p className={styles.none}>
        <Film size={14} aria-hidden />
        {captureNote(state)}
      </p>
    );
  }

  return (
    <div className={styles.wrap}>
      <video
        className={styles.video}
        // Remount on change so the browser loads the newly chosen file
        // rather than keeping the one it already has.
        key={showing.name}
        src={source ?? undefined}
        controls
        loop
        muted
        playsInline
        preload="metadata"
      />
      <div className={styles.row}>
        {available.length > 1 &&
          available.map(option => (
            <button
              key={option.key}
              type="button"
              className={`${styles.pick} ${option.key === showing.key ? styles.pickOn : ''}`}
              onClick={() => setChosen(option.key)}
            >
              {option.label}
            </button>
          ))}
        <span className={styles.note}>
          <Gauge size={12} aria-hidden />
          {showing.key === 'dense'
            ? `${denseFrames ?? '?'} frames at stream rate`
            : 'sampled while the watcher was working'}
        </span>
      </div>
    </div>
  );
};
