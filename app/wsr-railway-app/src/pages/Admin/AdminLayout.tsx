import { NavLink, Outlet } from 'react-router-dom';
import { isFirebaseConfigured } from '../../firebase';
import styles from './Admin.module.css';

const SECTIONS = [
  { to: '/admin', end: true, label: 'Overview' },
  { to: '/admin/verify', label: 'Verify' },
  { to: '/admin/episodes', label: 'Detections' },
  { to: '/admin/cameras', label: 'Cameras' },
];

export const AdminLayout: React.FC = () => (
  <div className="container">
    <div className="contentWrapper">
      <div className={styles.masthead}>
        <div>
          <p className={styles.eyebrow}>Detection system</p>
          <h1 className={styles.title}>Control Room</h1>
        </div>
        <span className={isFirebaseConfigured ? styles.connected : styles.offline}>
          {isFirebaseConfigured ? 'Firestore connected' : 'Firestore not configured'}
        </span>
      </div>

      <nav className={styles.tabs}>
        {SECTIONS.map(section => (
          <NavLink
            key={section.to}
            to={section.to}
            end={section.end}
            className={({ isActive }) =>
              `${styles.tab} ${isActive ? styles.tabActive : ''}`}
          >
            {section.label}
          </NavLink>
        ))}
      </nav>

      <Outlet />
    </div>
  </div>
);
