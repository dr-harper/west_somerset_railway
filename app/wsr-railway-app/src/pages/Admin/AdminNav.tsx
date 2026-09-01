import { NavLink } from 'react-router-dom';
import { Cctv, CircleCheckBig, Gauge, Settings, TrainFront, Waypoints } from 'lucide-react';
import styles from './AdminNav.module.css';

/**
 * Getting between the control room's sections.
 *
 * The sections are a fixed, short list that never changes, which is what a
 * rail is for: on a desktop it is always visible, so where you are and what
 * else exists are both answered without a click. On a phone the same list
 * goes to the bottom of the screen, within reach of a thumb — this gets
 * used standing on a platform, not sitting at a desk.
 */

export interface Section {
  to: string;
  end?: boolean;
  label: string;
  short: string;
  icon: typeof Gauge;
}

export const SECTIONS: Section[] = [
  { to: '/admin', end: true, label: 'Overview', short: 'Overview', icon: Gauge },
  { to: '/admin/events', label: 'Events', short: 'Events', icon: Waypoints },
  { to: '/admin/trains', label: 'Trains', short: 'Trains', icon: TrainFront },
  { to: '/admin/cameras', label: 'Cameras', short: 'Cameras', icon: Cctv },
  { to: '/admin/verify', label: 'Verify', short: 'Verify', icon: CircleCheckBig },
  { to: '/admin/settings', label: 'Settings', short: 'Set-up', icon: Settings },
];

interface Props {
  /** Sections with something needing attention, e.g. { '/admin': 2 }. */
  badges?: Record<string, number>;
}

export const AdminRail: React.FC<Props> = ({ badges = {} }) => (
  <nav className={styles.rail} aria-label="Control room sections">
    {SECTIONS.map(({ to, end, label, icon: Icon }) => (
      <NavLink
        key={to}
        to={to}
        end={end}
        className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ''}`}
      >
        <span className={styles.icon}><Icon size={16} aria-hidden /></span>
        {label}
        {badges[to] ? (
          <span className={styles.badge} aria-label={`${badges[to]} need attention`}>
            {badges[to]}
          </span>
        ) : null}
      </NavLink>
    ))}
  </nav>
);

export const AdminBar: React.FC<Props> = ({ badges = {} }) => (
  <nav className={styles.bar} aria-label="Control room sections">
    {SECTIONS.map(({ to, end, short, icon: Icon }) => (
      <NavLink
        key={to}
        to={to}
        end={end}
        className={({ isActive }) => `${styles.barLink} ${isActive ? styles.barActive : ''}`}
      >
        <Icon size={18} aria-hidden />
        {short}
        {badges[to] ? (
          <span className={styles.barBadge} aria-label={`${badges[to]} need attention`}>
            {badges[to]}
          </span>
        ) : null}
      </NavLink>
    ))}
  </nav>
);
