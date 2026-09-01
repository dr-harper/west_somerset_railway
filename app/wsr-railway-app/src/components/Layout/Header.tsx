import React from 'react';
import { NavLink } from 'react-router-dom';
import styles from './Header.module.css';

/**
 * Site navigation.
 *
 * NavLink rather than comparing pathnames by hand: it sets aria-current on
 * the active item, which the manual version never did, so a screen reader
 * had no way to tell which page it was on.
 *
 * The control room sits apart from the timetable links. It is for whoever
 * is running the detection system, not for someone catching a train, and
 * putting it in the same row implies it is another way to look up a
 * departure.
 */

const PAGES = [
  { to: '/', label: 'Departures', end: true },
  { to: '/live-trains', label: 'Trains Today' },
  { to: '/journey-planner', label: 'Journey Planner' },
];

export const Header: React.FC = () => (
  <header className={styles.header}>
    <div className="container">
      <div className="container-narrow">
        <div className={styles.headerContent}>
          <NavLink to="/" className={styles.logo}>
            <img
              src={`${import.meta.env.BASE_URL}west_somerset_railway.png`}
              alt=""
              className={styles.logoImage}
            />
            {/* The gap between the two halves is a real space, not just CSS.
                Spaced with `gap` alone the text read as one run-together
                word to a screen reader and when copied. */}
            <h1 className={styles.title}>
              <span className={styles.titleLead}>West Somerset Railway</span>{' '}
              <span className={styles.titleTail}>Timetables</span>
            </h1>
          </NavLink>

          {/* One row that scrolls rather than a block that wraps. Four
              uppercase labels wrapped onto five ragged lines on a phone and
              took a third of the screen before any content. */}
          <nav className={styles.nav} aria-label="Site">
            {PAGES.map(page => (
              <NavLink
                key={page.to}
                to={page.to}
                end={page.end}
                className={({ isActive }) =>
                  `${styles.navLink} ${isActive ? styles.active : ''}`}
              >
                {page.label}
              </NavLink>
            ))}
            <NavLink
              to="/admin"
              className={({ isActive }) =>
                `${styles.navLink} ${styles.adminLink} ${isActive ? styles.active : ''}`}
              title="Detection system control room"
            >
              Control Room
            </NavLink>
          </nav>
        </div>
      </div>
    </div>
  </header>
);
