import { useEffect, useState } from 'react';
import {
  onAuthStateChanged,
  signInWithPopup,
  signInWithRedirect,
  signOut,
  type User,
} from 'firebase/auth';
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

/**
 * Local development skips the sign-in gate.
 *
 * The gate protects nothing on a laptop: the emulator holds a copy of the
 * day's detections on this machine alone, and the stills come off the disk
 * they were written to. All it did was put a popup between the operator and
 * the tools, and when that popup failed to open the button sat there doing
 * nothing at all.
 *
 * Guarded on DEV as well as the flag, so a production build cannot have it
 * however the variable is set — an auth bypass that can be switched on by
 * environment is not a bypass anyone should be able to reach.
 */
const SKIP_AUTH = import.meta.env.DEV && import.meta.env.VITE_SKIP_AUTH === '1';

export interface Operator {
  state: OperatorState;
  user: User | null;
  /** Why the last sign-in attempt got nowhere, for the page to say out loud. */
  problem: string | null;
  signIn: () => Promise<void>;
  signOutNow: () => Promise<void>;
}

/**
 * Sign-in failures, in words rather than error codes.
 *
 * The button used to await signInWithPopup with nothing around it, so every
 * failure became an unhandled promise rejection: clicking did nothing at
 * all, with nothing on screen and nothing in the console to chase. A gate
 * that silently refuses is worse than one that refuses loudly.
 */
function explain(code: string | undefined): string {
  switch (code) {
    case 'auth/popup-blocked':
      return 'The browser blocked the sign-in window. Retrying in this tab…';
    case 'auth/network-request-failed':
      return 'Could not reach the sign-in service.';
    case 'auth/unauthorized-domain':
      return 'This address is not on the sign-in allowlist for the project.';
    default:
      return `Sign-in failed${code ? ` (${code})` : ''}.`;
  }
}

export function useOperator(): Operator {
  const [user, setUser] = useState<User | null>(null);
  const [state, setState] = useState<OperatorState>(
    SKIP_AUTH ? 'unavailable'
      : isFirebaseConfigured && auth ? 'loading'
      : 'unavailable');
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    if (SKIP_AUTH || !auth) return;
    return onAuthStateChanged(auth, next => {
      setUser(next);
      setState(next ? 'signed-in' : 'signed-out');
    });
  }, []);

  return {
    state,
    user,
    problem,
    signIn: async () => {
      if (!auth || !googleProvider) {
        setProblem('Sign-in is not configured in this build.');
        return;
      }
      setProblem(null);
      // Against the Auth emulator, redirect rather than popup. The popup
      // never opened and never rejected — the emulator logged no handler
      // request at all — so the button sat there doing nothing, which is
      // the least debuggable failure there is. Redirect needs no popup,
      // survives a blocker, and the emulator's account chooser comes back
      // to this tab. Deployed sign-in keeps the popup, which does not lose
      // whatever the operator was looking at.
      if (import.meta.env.VITE_AUTH_EMULATOR) {
        await signInWithRedirect(auth, googleProvider);
        return;
      }
      try {
        await signInWithPopup(auth, googleProvider);
      } catch (error) {
        const code = (error as { code?: string })?.code;
        // Closing the window, or clicking twice, is not a failure worth
        // reporting — the person did it on purpose.
        if (code === 'auth/popup-closed-by-user'
            || code === 'auth/cancelled-popup-request') return;
        // A blocked popup is the ordinary case on a fresh browser profile,
        // and redirecting this tab needs no popup at all. Falling back is
        // better than telling someone to go and change a browser setting.
        if (code === 'auth/popup-blocked'
            || code === 'auth/operation-not-supported-in-this-environment') {
          setProblem(explain(code));
          try {
            await signInWithRedirect(auth, googleProvider);
            return;
          } catch (redirectError) {
            setProblem(explain((redirectError as { code?: string })?.code));
            return;
          }
        }
        console.error('sign-in failed', error);
        setProblem(explain(code));
      }
    },
    signOutNow: async () => {
      if (auth) await signOut(auth);
    },
  };
}
