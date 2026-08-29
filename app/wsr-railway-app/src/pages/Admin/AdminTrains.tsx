import { useEffect, useMemo, useState } from 'react';
import { isFirebaseConfigured } from '../../firebase';
import { cameraName } from '../../services/cameras';
import { delayLabel } from '../../services/episodeText';
import {
  fetchMovements,
  groupByTrain,
  type Movement,
} from '../../utils/firestore/movements';
import styles from './Admin.module.css';

/**
 * The day organised by train rather than by time.
 *
 * "What did D7017 do today" is the question an operator actually asks, and
 * it is the one the episode list cannot answer — a train appears there as
 * a scatter of unrelated rows at six cameras. Grouping the movements by
 * traction turns those back into a working.
 */

function delayClass(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '';
  if (Math.abs(minutes) < 1) return styles.onTime;
  return minutes > 3 ? styles.late : '';
}

const MovementRow: React.FC<{ movement: Movement }> = ({ movement }) => (
  <div className={styles.movement}>
    <div className={styles.movementHead}>
      <span className={styles.mono}>
        {movement.first_seen}–{movement.last_seen}
      </span>
      <span className={styles.movementRoute}>
        {movement.from} → {movement.to}
      </span>
      <span className={styles.muted}>
        {movement.miles} mi
        {movement.avg_mph ? ` · ${movement.avg_mph} mph` : ''}
      </span>
      {movement.kind === 'scheduled' ? (
        // How it finished, not the mean over the run: a train 11 early at
        // the start and 1 late at the end averages out to "5 early", which
        // describes no moment of the journey and contradicts the detail
        // line directly underneath.
        <span className={`${styles.badge} ${delayClass(movement.delay_end_min ?? movement.delay_min)}`}>
          {movement.booked_departure} ·{' '}
          {delayLabel(movement.delay_end_min ?? movement.delay_min)}
        </span>
      ) : (
        <span className={`${styles.badge} ${styles.corrected}`}>unscheduled</span>
      )}
    </div>

    {/* Where it was seen, in order — the evidence behind the claim. */}
    <ol className={styles.sightings}>
      {movement.observations.map((sighting, index) => (
        <li key={`${sighting.at}-${index}`}>
          <span className={styles.mono}>{sighting.at.slice(0, 5)}</span>{' '}
          {cameraName(sighting.camera)}
          {sighting.conf ? (
            <span className={styles.muted}> {Math.round(sighting.conf * 100)}%</span>
          ) : null}
        </li>
      ))}
    </ol>

    {movement.kind === 'scheduled' &&
      movement.delay_start_min !== null &&
      movement.delay_end_min !== null && (
        <p className={styles.muted}>
          Ran {delayLabel(movement.delay_start_min)} at the start and{' '}
          {delayLabel(movement.delay_end_min)} by the end
          {Math.abs(
            (movement.delay_end_min ?? 0) - (movement.delay_start_min ?? 0)
          ) >= 1
            ? `, ${
                (movement.delay_end_min ?? 0) > (movement.delay_start_min ?? 0)
                  ? 'losing'
                  : 'regaining'
              } ${Math.abs(
                Math.round(
                  (movement.delay_end_min ?? 0) - (movement.delay_start_min ?? 0)
                )
              )} minutes en route`
            : ''}
          .
        </p>
      )}
  </div>
);

export const AdminTrains: React.FC = () => {
  const [movements, setMovements] = useState<Movement[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState<string | null>(null);

  useEffect(() => {
    if (!isFirebaseConfigured) {
      setLoading(false);
      return;
    }
    fetchMovements(undefined, 300)
      .then(setMovements)
      .catch(cause => console.error('Failed to load movements', cause))
      .finally(() => setLoading(false));
  }, []);

  const trains = useMemo(() => groupByTrain(movements), [movements]);
  const identified = trains.filter(t => t.loco);
  const unidentified = trains.filter(t => !t.loco);

  if (!isFirebaseConfigured) {
    return <div className={styles.panel}>Firestore is not configured.</div>;
  }
  if (loading) return <div className={styles.panel}>Loading movements…</div>;
  if (!movements.length) {
    return (
      <div className={styles.panel}>
        <h2>No movements yet</h2>
        <p className={styles.muted}>
          Movements are built by chaining detections across cameras. Upload a
          day's run with{' '}
          <code>python3 upload_episodes.py --project demo-wsr</code>.
        </p>
      </div>
    );
  }

  return (
    <>
      <div className={styles.statRow}>
        <div className={styles.stat}>
          <span className={styles.statValue}>{movements.length}</span>
          <span className={styles.statLabel}>movements</span>
        </div>
        <div className={styles.stat}>
          <span className={styles.statValue}>{identified.length}</span>
          <span className={styles.statLabel}>trains identified</span>
        </div>
        <div className={styles.stat}>
          <span className={`${styles.statValue} ${styles.accent}`}>
            {movements.filter(m => m.kind === 'unscheduled').length}
          </span>
          <span className={styles.statLabel}>not in the timetable</span>
        </div>
      </div>

      {identified.map(train => (
        <div key={train.key} className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>
              {train.loco}
              {train.serviceType ? (
                <span className={styles.muted}> · {train.serviceType}</span>
              ) : null}
            </h2>
            <button
              className={styles.action}
              onClick={() => setOpen(open === train.key ? null : train.key)}
            >
              {open === train.key ? 'Hide runs' : `${train.movements.length} runs`}
            </button>
          </div>
          <p className={styles.muted}>
            {train.sightings} sightings across {Math.round(train.miles)} miles
          </p>
          {open === train.key &&
            train.movements.map(movement => (
              <MovementRow key={movement.id} movement={movement} />
            ))}
        </div>
      ))}

      {unidentified.length > 0 && (
        <div className={styles.panel}>
          <div className={styles.panelHead}>
            <h2>Not yet identified</h2>
            <button
              className={styles.action}
              onClick={() => setOpen(open === 'unidentified' ? null : 'unidentified')}
            >
              {open === 'unidentified' ? 'Hide' : 'Show'}
            </button>
          </div>
          <p className={styles.muted}>
            {unidentified.reduce((n, t) => n + t.movements.length, 0)} movements
            with no traction read from the stills. These are the ones worth
            tagging by hand.
          </p>
          {open === 'unidentified' &&
            unidentified.flatMap(train =>
              train.movements.map(movement => (
                <MovementRow key={movement.id} movement={movement} />
              ))
            )}
        </div>
      )}
    </>
  );
};
