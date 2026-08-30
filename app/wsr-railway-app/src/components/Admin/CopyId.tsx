import { useRef, useState } from 'react';
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

/**
 * Put text on the clipboard, whatever the page is served over.
 *
 * navigator.clipboard exists only in a secure context, and the control
 * room is reached over plain HTTP on the local network — so on the device
 * it is most used from, the modern API is simply absent. execCommand is
 * deprecated but works there, and is the reason this has a fallback at
 * all rather than a button that silently does nothing.
 */
async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch {
      // fall through to the older route
    }
  }
  const holder = document.createElement('textarea');
  holder.value = text;
  // Off-screen rather than hidden: a display:none element cannot be
  // selected, and the selection is what execCommand copies.
  holder.style.position = 'fixed';
  holder.style.left = '-9999px';
  holder.setAttribute('readonly', '');
  document.body.appendChild(holder);
  try {
    holder.select();
    holder.setSelectionRange(0, text.length);
    return document.execCommand('copy');
  } catch {
    return false;
  } finally {
    document.body.removeChild(holder);
  }
}

export const CopyId: React.FC<Props> = ({ id, short = false, label }) => {
  const [state, setState] = useState<'idle' | 'copied' | 'failed'>('idle');
  const text = useRef<HTMLElement>(null);

  const copy = async (event: React.MouseEvent) => {
    event.stopPropagation();
    const done = await copyText(id);
    setState(done ? 'copied' : 'failed');
    if (!done && text.current) {
      // Neither route was allowed. Select the id instead so the keyboard
      // shortcut works — a button that reports failure and leaves you to
      // retype a 25-character id has not helped.
      const range = document.createRange();
      range.selectNodeContents(text.current);
      const selection = window.getSelection();
      selection?.removeAllRanges();
      selection?.addRange(range);
    }
    window.setTimeout(() => setState('idle'), done ? 1500 : 4000);
  };

  return (
    <button
      type="button"
      className={`${styles.chip} ${state === 'failed' ? styles.failed : ''}`}
      onClick={copy}
      title={state === 'failed' ? id : `Copy ${id}`}
      aria-label={`Copy identifier ${id}`}
    >
      {label && <span className={styles.label}>{label}</span>}
      <code className={styles.id} ref={text}>
        {state === 'failed' ? id : short ? shorten(id) : id}
      </code>
      {state === 'copied' ? <Check size={12} aria-hidden /> : <Copy size={12} aria-hidden />}
    </button>
  );
};
