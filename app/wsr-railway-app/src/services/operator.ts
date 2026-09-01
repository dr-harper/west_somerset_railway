import { useEffect, useState } from 'react';
import { onAuthStateChanged, signInWithPopup, signOut, type User } from 'firebase/auth';
import { auth, googleProvider, isFirebaseConfigured } from '../firebase';

/**
 * Who is operating the control room.
 *
 * Sign-in used to sit on the verification page alone, so the rest of the
 * control room — every detection, the camera setup, the tracing tool — was
 * reachable by anyone who knew the path. The data behind it is public on
 * purpose (the timetable's "seen at" panel is built on the same detections),
 * but the operator's tools are not a public exhibit.
 *
 * Signing in is not the same as being allowed to change anything. Writing a
 * verification needs a grant under /verifiers, which the rules check and
 * nobody can give themselves.
 */

export type OperatorState = 'loading' | 'signed-out' | 'signed-in' | 'unavailable';

export interface Operator {
  state: OperatorState;
  user: User | null;
  signIn: () => Promise<void>;
  signOutNow: () => Promise<void>;
}

export function useOperator(): Operator {
  const [user, setUser] = useState<User | null>(null);
  const [state, setState] = useState<OperatorState>(
    isFirebaseConfigured && auth ? 'loading' : 'unavailable');

  useEffect(() => {
    if (!auth) return;
    return onAuthStateChanged(auth, next => {
      setUser(next);
      setState(next ? 'signed-in' : 'signed-out');
    });
  }, []);

  return {
    state,
    user,
    signIn: async () => {
      if (auth && googleProvider) await signInWithPopup(auth, googleProvider);
    },
    signOutNow: async () => {
      if (auth) await signOut(auth);
    },
  };
}
