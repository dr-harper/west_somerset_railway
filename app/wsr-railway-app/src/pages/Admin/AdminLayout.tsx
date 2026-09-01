import { Outlet } from 'react-router-dom';
import { LogOut } from 'lucide-react';
import { isFirebaseConfigured } from '../../firebase';
import { useOperator } from '../../services/operator';
import { AdminBar, AdminRail } from './AdminNav';
import styles from './Admin.module.css';
import nav from './AdminNav.module.css';

/**
 * The control room shell.
 *
 * The sections used to sit in a row of tabs, which fitted neither size:
 * desktop had width going spare beside a single narrow column, and on a
 * phone the row scrolled sideways so Verify and Settings were off the edge
 * and effectively hidden. A rail on the left and a bar under the thumb suit
 * the two cases the tool is actually used in.
 */

export const AdminLayout: React.FC = () => {
  const operator = useOperator();

  return (
  <div className="container">
    <div className="contentWrapper">
      <div className={styles.masthead}>
        <div>
          <p className={styles.eyebrow}>Detection system</p>
          <h1 className={styles.title}>Control Room</h1>
        </div>
        <div className={styles.mastheadRight}>
          <span className={isFirebaseConfigured ? styles.connected : styles.offline}>
            {isFirebaseConfigured ? 'Firestore connected' : 'Firestore not configured'}
          </span>
          {operator.state === 'signed-in' && (
            <button className={styles.signOut} onClick={operator.signOutNow}>
              <LogOut size={13} aria-hidden />
              {operator.user?.email ?? 'Sign out'}
            </button>
          )}
        </div>
      </div>

      {/* The detections themselves are public — the timetable's "seen at"
          panel is built on them. The operator's tools are not, so the shell
          asks who you are before it draws them. Signing in is not the same
          as being allowed to change anything: writing a verification needs a
          grant under /verifiers that nobody can give themselves. */}
      {operator.state === 'signed-in' || operator.state === 'unavailable' ? (
        <>
          <div className={nav.shell}>
            <AdminRail />
            <main className={nav.main}>
              <Outlet />
            </main>
          </div>
          <AdminBar />
        </>
      ) : (
        <div className={styles.panel}>
          <h2>{operator.state === 'loading' ? 'Checking…' : 'Control room'}</h2>
          {operator.state === 'signed-out' && (
            <>
              <p className={styles.muted}>
                Sign in to see the detections, cameras and tracing tools.
              </p>
              <button className={styles.action} onClick={operator.signIn}>
                Sign in
              </button>
            </>
          )}
        </div>
      )}
    </div>
  </div>
  );
};
