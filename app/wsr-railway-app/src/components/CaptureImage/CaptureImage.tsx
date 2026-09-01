import { ImageOff, Lock } from 'lucide-react';
import { captureNote, useCapture } from '../../services/captures';
import styles from './CaptureImage.module.css';

/**
 * A still, or an honest account of why there isn't one.
 *
 * Deployed, these come from a private bucket over the signed-in user's own
 * token, so "no picture" now has several quite different causes: nothing was
 * recorded, the file has gone, or this viewer is not an operator and the
 * footage is not theirs to see. An <img> with a dead src collapses all three
 * into the same grey box, which is how the control room came to look broken
 * when it was in fact working exactly as its rules say.
 */

interface Props {
  filename: string | null | undefined;
  alt: string;
  className?: string;
  /** Off-screen thumbnails in a long list should not all fetch at once. */
  loading?: 'lazy' | 'eager';
}

export const CaptureImage: React.FC<Props> = ({ filename, alt, className, loading = 'lazy' }) => {
  const { url, state } = useCapture(filename);

  if (state === 'ready' && url) {
    return <img src={url} alt={alt} loading={loading} className={className} />;
  }

  if (state === 'loading') {
    return <span className={`${styles.placeholder} ${styles.pending}`} aria-hidden />;
  }

  return (
    <span className={styles.placeholder}>
      {state === 'forbidden' ? <Lock size={14} aria-hidden /> : <ImageOff size={14} aria-hidden />}
      <span className={styles.note}>{captureNote(state)}</span>
    </span>
  );
};
