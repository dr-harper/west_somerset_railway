import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import styles from './Header.module.css';

export const Header: React.FC = () => {
  const location = useLocation();

  return (
    <header className={styles.header}>
      <div className="container">
        <div className="container-narrow">
          <div className={styles.headerContent}>
            <div className={styles.logo}>
              <img src={`${import.meta.env.BASE_URL}west_somerset_railway.png`} alt="WSR Logo" className={styles.logoImage} />
              <div>
                <h1 className={styles.title}>West Somerset Railway Timetables</h1>
              </div>
            </div>
            <nav className={styles.nav}>
              <Link
                to="/"
                className={`${styles.navLink} ${location.pathname === '/' ? styles.active : ''}`}
              >
                Departures
              </Link>
              <Link
                to="/live-trains"
                className={`${styles.navLink} ${location.pathname === '/live-trains' ? styles.active : ''}`}
              >
                Live Trains
              </Link>
              <Link
                to="/journey-planner"
                className={`${styles.navLink} ${location.pathname === '/journey-planner' ? styles.active : ''}`}
              >
                Journey Planner
              </Link>
              <Link
                to="/admin"
                className={`${styles.navLink} ${styles.adminLink} ${location.pathname.startsWith('/admin') ? styles.active : ''}`}
                title="Detection system control room"
              >
                Control Room
              </Link>
            </nav>
          </div>
        </div>
      </div>
    </header>
  );
};