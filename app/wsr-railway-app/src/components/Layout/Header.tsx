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
              <img src="./west_somerset_railway.png" alt="WSR Logo" className={styles.logoImage} />
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
              <a href="#journey" className={styles.navLink}>Journey Planner</a>
              <a href="#about" className={styles.navLink}>About</a>
            </nav>
          </div>
        </div>
      </div>
    </header>
  );
};