import React from 'react';
import styles from './Footer.module.css';

export const Footer: React.FC = () => {
  return (
    <footer className={styles.footer}>
      <div className="container">
        <div className="container-narrow">
          <div className={styles.footerContent}>
            <div className={styles.footerSection}>
              <h3>About WSR</h3>
              <p>
                The West Somerset Railway is a heritage railway that runs along
                the beautiful Somerset coast. Operating since 1862, we preserve
                the golden age of steam travel.
              </p>
            </div>
            <div className={styles.footerSection}>
              <h3>Quick Links</h3>
              <ul>
                <li><a href="#timetables">Timetables</a></li>
                <li><a href="#tickets">Tickets & Fares</a></li>
                <li><a href="#events">Special Events</a></li>
                <li><a href="#contact">Contact Us</a></li>
              </ul>
            </div>
            <div className={styles.footerSection}>
              <h3>Contact Information</h3>
              <p>
                The Railway Station<br />
                Minehead<br />
                Somerset TA24 5BG<br />
                Tel: 01643 704996
              </p>
            </div>
          </div>
          <div className={styles.copyright}>
            <p>
              &copy; {new Date().getFullYear()} West Somerset Railway. All rights reserved.<br />
              Site by Mikey Harper.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};