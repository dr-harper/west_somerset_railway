import React from 'react';
import styles from './Header.module.css';

export const Header: React.FC = () => {
  return (
    <header className={styles.header}>
      <div className="container">
        <div className="container-narrow">
          <div className={styles.headerContent}>
            <div className={styles.logo}>
              <img src="/west_somerset_railway.png" alt="WSR Logo" className={styles.logoImage} />
              <div>
                <h1 className={styles.title}>West Somerset Railway Timetables</h1>
              </div>
            </div>
            <nav className={styles.nav}>
              <a href="#departures" className={styles.navLink}>Departures</a>
              <a href="#journey" className={styles.navLink}>Journey Planner</a>
              <a href="#about" className={styles.navLink}>About</a>
            </nav>
          </div>
        </div>
      </div>
    </header>
  );
};