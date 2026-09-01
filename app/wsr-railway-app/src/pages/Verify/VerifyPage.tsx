import { useCallback, useEffect, useState } from 'react';
import { onAuthStateChanged, signInWithPopup, signOut, type User } from 'firebase/auth';
import { auth, googleProvider, isFirebaseConfigured } from '../../firebase';
import {
  fetchEpisodes,
  verifyEpisode,
  type Episode,
  type VerificationStatus,
} from '../../utils/firestore/episodes';
import { cameraName } from '../../services/cameras';
import { captureUrl } from '../../services/captures';
import { EpisodeClip } from '../../components/Admin/EpisodeClip';
import styles from './VerifyPage.module.css';
import { observations, timetableNote } from '../../services/evidence';

export const VerifyPage: React.FC = () => {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
  const [seen, setSeen] = useState<string | null>(null);
  const [stopped, setStopped] = useState(false);
  const [reviewed, setReviewed] = useState(0);
  const [user, setUser] = useState<User | null>(null);
  const [checkingAuth, setCheckingAuth] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setEpisodes(await fetchEpisodes('unverified', 200));
      setError(null);
    } catch (cause) {
      console.error('Failed to load episodes', cause);
      setError('Could not load episodes. Is Firestore reachable?');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!auth) {
      setCheckingAuth(false);
      return;
    }
    return onAuthStateChanged(auth, signedIn => {
      setUser(signedIn);
      setCheckingAuth(false);
    });
  }, []);

  useEffect(() => {
    if (isFirebaseConfigured) load();
    else setLoading(false);
  }, [load]);

  const signIn = async () => {
    if (!auth) return;
    try {
      await signInWithPopup(auth, googleProvider);
      setError(null);
    } catch (cause) {
      console.error('Sign-in failed', cause);
      setError('Sign-in failed. Verification needs an approved account.');
    }
  };

  const current = episodes[index];

  const record = async (status: Exclude<VerificationStatus, 'unverified'>) => {
    if (!current) return;
    try {
      // What a person saw in the clip is worth more than the note field:
      // direction is the field the pipeline gets wrong on 97% of records,
      // and whether a train stopped is not in the data at all.
      await verifyEpisode(current.id, status, {
        ...(notes ? { notes } : {}),
        ...(seen ? { observedDirection: seen } : {}),
        ...(stopped ? { observedStopped: true } : {}),
      });
      setReviewed(count => count + 1);
      setNotes('');
      setSeen(null);
      setStopped(false);
      setIndex(i => i + 1);
    } catch (cause) {
      console.error('Failed to save verification', cause);
      setError(
        user
          ? 'That account is not approved to verify detections.'
          : 'Sign in before recording an answer.'
      );
    }
  };

  if (!isFirebaseConfigured) {
    return (
      <div className="container">
        <div className="contentWrapper">
          <div className={styles.notice}>
            <h1>Verification unavailable</h1>
            <p>
              Set the <code>VITE_FIREBASE_PROJECT_ID</code> environment variable
              to review detected trains. The timetable works without it.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <div className="contentWrapper">
        <div className={styles.header}>
          <h1 className={styles.title}>Verify Detections</h1>
          <p className={styles.subtitle}>
            Confirm what the cameras saw, so the tracker can learn from it
          </p>
          {!checkingAuth && (
            <div className={styles.account}>
              {user ? (
                <>
                  <span>Signed in as {user.displayName ?? user.email ?? 'verifier'}</span>
                  <button className={styles.link} onClick={() => auth && signOut(auth)}>
                    Sign out
                  </button>
                </>
              ) : (
                <button className={styles.secondary} onClick={signIn}>
                  Sign in to verify
                </button>
              )}
            </div>
          )}
        </div>

        {error && <div className={styles.error}>{error}</div>}

        {loading ? (
          <div className={styles.notice}>Loading detections…</div>
        ) : !current ? (
          <div className={styles.notice}>
            <h2>All caught up</h2>
            <p>
              {reviewed > 0
                ? `You reviewed ${reviewed} detection${reviewed === 1 ? '' : 's'}.`
                : 'Nothing is waiting to be verified.'}
            </p>
            <button className={styles.secondary} onClick={load}>Check again</button>
          </div>
        ) : (
          <div className={styles.card}>
            <div className={styles.progress}>
              {index + 1} of {episodes.length} waiting
            </div>

            <div className={styles.imageFrame}>
              {current.keyframe ? (
                <img
                  className={styles.image}
                  src={captureUrl(current.keyframe) ?? ''}
                  alt={`Detection at ${cameraName(current.camera)}`}
                />
              ) : (
                <div className={styles.imagePlaceholder}>No keyframe saved</div>
              )}
            </div>

            {/* A still cannot show whether a train stopped or which way it
                went, which are the two things a person can settle at a
                glance from the video and the pipeline most often cannot. */}
            <EpisodeClip
              clip={current.clip}
              denseClip={current.dense_clip}
              denseFrames={current.dense_frames}
            />

            {/* The evidence, before any conclusion drawn from it. Asking
                someone to rule on "we think this is an unscheduled working"
                gave them nothing to rule with. */}
            <dl className={styles.evidence}>
              {observations(current).map(item => (
                <div key={item.label} className={styles.row}>
                  <dt className={styles.rowLabel}>{item.label}</dt>
                  <dd className={styles.rowValue}>
                    <span className={styles[item.confidence]}>{item.value}</span>
                    {item.basis && <em className={styles.basis}>{item.basis}</em>}
                  </dd>
                </div>
              ))}
            </dl>

            {(() => {
              const note = timetableNote(current);
              return (
                <div className={styles.derived}>
                  <span className={styles.derivedLabel}>{note.label}</span>
                  <strong className={styles.derivedValue}>{note.value}</strong>
                  {note.basis && <em className={styles.basis}>{note.basis}</em>}
                </div>
              );
            })()}

            {/* Recorded because the pipeline could not work it out on 97%
                of detections, and someone watching the clip can. Each answer
                is ground truth the tracker has never had. */}
            <div className={styles.watched}>
              <span className={styles.watchedLabel}>From the clip, which way?</span>
              <div className={styles.watchedRow}>
                {['towards Minehead', 'towards Bishops Lydeard', 'stayed put', 'could not tell']
                  .map(option => (
                    <button
                      key={option}
                      type="button"
                      className={`${styles.pick} ${seen === option ? styles.pickOn : ''}`}
                      onClick={() => setSeen(seen === option ? null : option)}
                    >
                      {option}
                    </button>
                  ))}
              </div>
              <label className={styles.stopCheck}>
                <input
                  type="checkbox"
                  checked={stopped}
                  onChange={event => setStopped(event.target.checked)}
                />
                it came to a stand
              </label>
            </div>

            <input
              className={styles.notes}
              placeholder="Add a note (optional) — e.g. the actual loco"
              value={notes}
              onChange={event => setNotes(event.target.value)}
            />

            {/* The question is the one the picture can answer. Whether it
                was the 13:25 is not something anyone can tell from a still,
                and asking made every answer worth less. */}
            <p className={styles.question}>Looking at this, was a train there?</p>
            <div className={styles.actions}>
              <button className={styles.confirm} onClick={() => record('confirmed')}>
                Yes, a train
              </button>
              <button className={styles.reject} onClick={() => record('rejected')}>
                No, not a train
              </button>
              <button className={styles.correct} onClick={() => record('corrected')}>
                A train, but this is wrong
              </button>
              <button className={styles.skip} onClick={() => setIndex(i => i + 1)}>
                Skip
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
