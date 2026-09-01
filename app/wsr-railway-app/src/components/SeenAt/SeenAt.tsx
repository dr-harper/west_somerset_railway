import { useState } from 'react';
import { Camera, Clock, Eye, EyeOff } from 'lucide-react';
import { CaptureImage } from '../CaptureImage/CaptureImage';
import { cameraName } from '../../services/cameras';
import type { Sighting } from '../../services/sightings';
import styles from './SeenAt.module.css';

/**
 * What the cameras actually saw of this call, against what was booked.
 *
 * The rest of the site says where a train should be. This says where one
 * was — with the photograph, because a still of the train at the platform
 * is the part nobody can argue with, and because on a heritage line the
 * question "what was it?" matters as much as "was it on time?".
 */

interface Props {
  sighting: Sighting | null;
  booked: string | null | undefined;
  /** Shown when nothing was seen, so silence is explained rather than blank. */
  stationName?: string;
}

function clock(iso: string): string {
  return iso.slice(11, 16);
}

function dwellText(seconds: number | null): string | null {
  if (seconds === null || seconds < 90) return null;
  return `stood ${Math.round(seconds / 60)} min`;
}

export const SeenAt: React.FC<Props> = ({ sighting, booked, stationName }) => {
  const [showStill, setShowStill] = useState(false);

  if (!sighting) {
    return (
      <p className={styles.unseen}>
        <EyeOff size={14} aria-hidden />
        Not seen by the cameras
        {stationName ? ` at ${stationName}` : ''} yet
      </p>
    );
  }

  const delta = sighting.deltaMinutes;
  const timing =
    delta === null
      ? null
      : Math.abs(delta) < 1
        ? 'on time'
        : delta > 0
          ? `${delta} min after booked`
          : `${-delta} min before booked`;

  // Prefer the high-resolution frame and fall back to the keyframe, picking
  // the file before asking for it rather than requesting both.
  const still = sighting.episodes[0]?.hires ?? sighting.episodes[0]?.keyframe;
  const dwell = dwellText(sighting.dwellSeconds);

  return (
    <div className={styles.seen}>
      <p className={styles.headline}>
        <Eye size={14} aria-hidden />
        <strong>Seen {clock(sighting.firstSeen)}</strong>
        {sighting.lastSeen && sighting.lastSeen !== sighting.firstSeen && (
          <> &rarr; {clock(sighting.lastSeen)}</>
        )}
        {booked && (
          <span className={styles.muted}>
            {' '}&middot; booked {booked}
            {timing ? `, ${timing}` : ''}
          </span>
        )}
      </p>

      <p className={styles.detail}>
        {dwell && (
          <span>
            <Clock size={12} aria-hidden /> {dwell}
          </span>
        )}
        <span>
          <Camera size={12} aria-hidden />
          {sighting.cameras.length > 1
            ? `${sighting.cameras.length} cameras agree`
            : cameraName(sighting.cameras[0])}
        </span>
        {still && (
          <button
            type="button"
            className={styles.toggle}
            onClick={() => setShowStill(value => !value)}
            aria-expanded={showStill}
          >
            {showStill ? 'Hide photo' : 'Show photo'}
          </button>
        )}
      </p>

      {showStill && still && (
        <CaptureImage
          className={styles.still}
          filename={still}
          alt={`The train seen at ${sighting.station} at ${clock(sighting.firstSeen)}`}
        />
      )}
    </div>
  );
};
