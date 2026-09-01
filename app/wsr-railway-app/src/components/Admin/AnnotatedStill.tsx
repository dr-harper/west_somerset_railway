import { useEffect, useState } from 'react';
import { Frame, Square, SquareDashed } from 'lucide-react';
import type { EpisodeBoxes } from '../../utils/firestore/episodes';
import { captureNote, useCapture } from '../../services/captures';
import styles from './AnnotatedStill.module.css';

/**
 * A detection still with its boxes drawn over it, not into it.
 *
 * The pipeline used to burn the zone polygons and detection boxes into the
 * saved JPEG. That made the annotation permanent: it could not be lifted
 * to read a running number underneath, and the only copy of the frame had
 * the overlay baked in, so anything reading it later — a classifier, or a
 * person identifying traction — was looking at the drawing as much as the
 * photograph. Boxes now travel as coordinates and are drawn as SVG on top,
 * which means they can be turned off.
 */

interface Props {
  /** File names, preferred first. The hi-res still is missing for some
   *  episodes, so the component falls through to the next rather than
   *  showing a broken image. */
  sources: (string | null | undefined)[];
  alt: string;
  boxes?: EpisodeBoxes | null;
}

export const AnnotatedStill: React.FC<Props> = ({ sources, alt, boxes }) => {
  const candidates = sources.filter((s): s is string => Boolean(s));
  const [index, setIndex] = useState(0);
  const [showBoxes, setShowBoxes] = useState(true);

  useEffect(() => setIndex(0), [candidates.join('|')]);

  const showing = candidates[index];
  const { url: src, state } = useCapture(showing);

  // Falling through to the next candidate is right when a file is absent
  // and wrong when access was refused: the second file lives in the same
  // bucket under the same rule, so retrying it only fails again more
  // slowly. Refusal is reported instead.
  useEffect(() => {
    if (state === 'missing') setIndex(current => current + 1);
  }, [state, showing]);

  if (!showing || state === 'missing') {
    return <p className={styles.noBoxes}>No still was saved for this detection.</p>;
  }
  if (state === 'forbidden') {
    return <p className={styles.noBoxes}>{captureNote(state)}.</p>;
  }
  if (!src) {
    return <p className={styles.noBoxes} aria-busy="true" />;
  }

  // Boxes were measured against one particular image. If we have fallen
  // back to a different one, the coordinates no longer describe it.
  const applies = Boolean(boxes && (!boxes.image || boxes.image === showing));
  const detections = applies ? (boxes?.detections ?? []) : [];
  const canToggle = detections.length > 0;

  return (
    <figure className={styles.figure}>
      <div className={styles.frame}>
        <img
          className={styles.image}
          src={src}
          alt={alt}
          onError={() => setIndex(current => current + 1)}
        />

        {canToggle && showBoxes && (
          <svg
            className={styles.overlay}
            viewBox={`0 0 ${boxes!.width} ${boxes!.height}`}
            preserveAspectRatio="none"
            aria-hidden
          >
            {detections.map((detection, i) => {
              const [x1, y1, x2, y2] = detection.box;
              return (
                <g key={i}>
                  <rect
                    className={styles.box}
                    x={x1}
                    y={y1}
                    width={x2 - x1}
                    height={y2 - y1}
                  />
                  <text className={styles.label} x={x1 + 4} y={Math.max(20, y1 - 6)}>
                    {Math.round(detection.conf * 100)}%
                    {detection.zone ? ` · ${detection.zone}` : ''}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>

      {canToggle ? (
        <button
          type="button"
          className={styles.toggle}
          onClick={() => setShowBoxes(value => !value)}
          aria-pressed={showBoxes}
        >
          {showBoxes ? <Square size={13} /> : <SquareDashed size={13} />}
          {showBoxes ? 'Hide boxes' : 'Show boxes'}
        </button>
      ) : (
        <span className={styles.noBoxes}>
          <Frame size={13} />
          No box data for this still
        </span>
      )}
    </figure>
  );
};
