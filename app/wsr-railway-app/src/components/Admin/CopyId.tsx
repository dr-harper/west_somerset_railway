import { useState } from 'react';
import { Check, Copy } from 'lucide-react';
import styles from './CopyId.module.css';

/**
 * The identifier a record is filed under, ready to be quoted.
 *
 * Every page here shows times and camera names, which are fine for
 * reading and useless for pointing at: two cameras watch some stations
 * and a busy minute holds several detections. The id is what the
 * pipeline, Firestore and the capture filenames all agree on, so it is
 * the thing to quote when something needs looking at.
 */

interface Props {
  id: string;
  /** Drop the leading date, which is the same for every row on a page. */
  short?: boolean;
  label?: string;
}

/**
 * The id without its date prefix.
 *
 * Ids look like 20260830T164154_watchet_1 or 20260830_0809_BL_BA, and on
 * a page showing one day the date is the least useful part. What must
 * survive is the time: trimming to the tail instead left two different
 * detections both reading 'williton_2'.
 */
function shorten(id: string): string {
  return id.replace(/^\d{8}T?_?/, '');
}

export const CopyId: React.FC<Props> = ({ id, short = false, label }) => {
  const [copied, setCopied] = useState(false);

  const copy = async (event: React.MouseEvent) => {
    event.stopPropagation();
    try {
      await navigator.clipboard.writeText(id);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be refused; the id is on screen regardless.
    }
  };

  return (
    <button
      type="button"
      className={styles.chip}
      onClick={copy}
      title={`Copy ${id}`}
      aria-label={`Copy identifier ${id}`}
    >
      {label && <span className={styles.label}>{label}</span>}
      <code className={styles.id}>{short ? shorten(id) : id}</code>
      {copied ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
    </button>
  );
};
