import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import { ENOUGH, stillNeeded, type Accuracy } from '../../services/accuracy';
import styles from './AccuracyPanel.module.css';

/**
 * How often the monitor is right, and how far off knowing that we are.
 *
 * Verification was a page nobody visited, because checking a detection
 * produced nothing an operator could see. Here the checking adds up to a
 * figure, and until there is enough of it the panel says so plainly rather
 * than reporting "100% correct" from two clicks.
 *
 * The corroboration line is kept separate and labelled as a proxy. It is
 * free and it covers only the six cameras with a working second view, so it
 * is evidence but never the answer.
 */

interface Props {
  accuracy: Accuracy;
}

export const AccuracyPanel: React.FC<Props> = ({ accuracy }) => {
  const needed = stillNeeded(accuracy);
  const share = accuracy.precision;

  return (
    <section className={styles.panel} aria-label="Measured accuracy">
      <div className={styles.head}>
        <h2 className={styles.title}>Accuracy</h2>
        <Link className={styles.action} to="/admin/verify">
          {needed > 0 ? `Check ${needed} more` : 'Keep checking'}
          <ArrowRight size={14} aria-hidden />
        </Link>
      </div>

      {share === null ? (
        <>
          <div className={styles.figure}>
            <span className={styles.value}>{accuracy.checked}</span>
            <span className={styles.margin}>of {ENOUGH} needed</span>
          </div>
          <p className={styles.caption}>
            Not enough detections have been checked to put a number on how often
            the monitor is right. {needed} more and this becomes a measurement
            rather than an estimate.
          </p>
          <div className={styles.bar}>
            <div
              className={styles.fill}
              style={{ width: `${Math.min(100, (accuracy.checked / ENOUGH) * 100)}%` }}
            />
          </div>
        </>
      ) : (
        <>
          <div className={styles.figure}>
            <span className={styles.value}>{Math.round(share * 100)}%</span>
            <span className={styles.margin}>
              &plusmn;{Math.round((accuracy.margin ?? 0) * 100)} points
            </span>
          </div>
          <p className={styles.caption}>
            of {accuracy.checked} checked detections were real trains. A corrected
            one still counts as real — the correction was to which service it was,
            not to whether it happened.
          </p>
        </>
      )}

      <div className={styles.split}>
        <span className={styles.stat}>
          <b>{accuracy.confirmed}</b><span>confirmed</span>
        </span>
        <span className={styles.stat}>
          <b>{accuracy.corrected}</b><span>corrected</span>
        </span>
        <span className={styles.stat}>
          <b>{accuracy.rejected}</b><span>rejected</span>
        </span>
        <span className={styles.stat}>
          <b>{accuracy.total - accuracy.checked}</b><span>not yet checked</span>
        </span>
      </div>

      {accuracy.checkable > 0 && (
        <p className={styles.proxy}>
          Separately, {accuracy.corroborated} of {accuracy.checkable} detections
          with a second camera on the same rails were seen by both. That is a free
          proxy, not a verdict — it says nothing about the five cameras with no
          second view.
        </p>
      )}
    </section>
  );
};
