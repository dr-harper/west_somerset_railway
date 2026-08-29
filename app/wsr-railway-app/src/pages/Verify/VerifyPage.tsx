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
import styles from './VerifyPage.module.css';

function describeClaim(episode: Episode): string {
  const { claim } = episode;
  if (claim.kind === 'unscheduled') {
    return 'Not in the timetable — an unscheduled working';
  }
  const parts = [`the ${claim.booked_departure}`];
  if (claim.loco) parts.push(claim.loco);
  else if (claim.serviceType) parts.push(claim.serviceType.toLowerCase());
  const delay = claim.delay_min;
  if (delay !== null && delay !== undefined) {
    parts.push(Math.abs(delay) < 1 ? 'on time'
      : delay > 0 ? `${Math.round(delay)} min late` : `${Math.round(-delay)} min early`);
  }
  return parts.join(', ');
}

export const VerifyPage: React.FC = () => {
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [index, setIndex] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notes, setNotes] = useState('');
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
      await verifyEpisode(current.id, status, notes ? { notes } : {});
      setReviewed(count => count + 1);
      setNotes('');
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

            <div className={styles.facts}>
              <div className={styles.where}>
                {cameraName(current.camera)}
              </div>
              <div className={styles.when}>
                {current.t_enter.slice(11, 16)}
                {current.t_exit ? `–${current.t_exit.slice(11, 16)}` : ''}
                {current.direction && current.direction !== 'unclear'
                  ? ` · ${current.direction}` : ''}
                {current.peak_conf ? ` · ${Math.round(current.peak_conf * 100)}% confident` : ''}
              </div>
            </div>

            <div className={styles.claim}>
              <span className={styles.claimLabel}>We think this is</span>
              <strong className={styles.claimText}>{describeClaim(current)}</strong>
              {current.claim.corroborating_sightings &&
                current.claim.corroborating_sightings > 1 && (
                <span className={styles.corroboration}>
                  seen by {current.claim.corroborating_sightings} cameras
                </span>
              )}
            </div>

            <input
              className={styles.notes}
              placeholder="Add a note (optional) — e.g. the actual loco"
              value={notes}
              onChange={event => setNotes(event.target.value)}
            />

            <div className={styles.actions}>
              <button className={styles.confirm} onClick={() => record('confirmed')}>
                Correct
              </button>
              <button className={styles.correct} onClick={() => record('corrected')}>
                Wrong train
              </button>
              <button className={styles.reject} onClick={() => record('rejected')}>
                Not a train
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
