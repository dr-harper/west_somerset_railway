import { Link } from 'react-router-dom';
import { AlertTriangle, ChevronRight, CircleCheck, Info, OctagonAlert } from 'lucide-react';
import type { Alert, Severity } from '../../services/health';
import styles from './HealthPanel.module.css';

/**
 * Whether the monitor is working, at the top of the page.
 *
 * The control room used to open on counts — detections, movements, cameras
 * reporting — which look identical on a day when nothing ran and a day when
 * the line was quiet. Every failure this system has had was silent, so the
 * first thing an operator sees now is whether anything is wrong, and only
 * then how much happened.
 */

interface Props {
  alerts: Alert[];
  /** When the assessment was made, so a stale page is obvious. */
  checkedAt?: Date;
}

const ICONS: Record<Severity, typeof Info> = {
  critical: OctagonAlert,
  warning: AlertTriangle,
  info: Info,
};

export const HealthPanel: React.FC<Props> = ({ alerts, checkedAt }) => {
  const time = checkedAt
    ? checkedAt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : null;

  return (
    <section className={styles.panel} aria-label="Monitor health">
      <div className={styles.head}>
        <h2 className={styles.title}>Health</h2>
        {time && <span className={styles.checked}>checked {time}</span>}
      </div>

      {alerts.length === 0 ? (
        <p className={styles.clear}>
          <CircleCheck size={17} aria-hidden />
          Capture is running, every camera has reported, and the pairs agree.
        </p>
      ) : (
        alerts.map(alert => {
          const Icon = ICONS[alert.severity];
          const inner = (
            <>
              <span className={styles.icon}><Icon size={17} aria-hidden /></span>
              <span className={styles.body}>
                <span className={styles.alertTitle}>{alert.title}</span>
                <p className={styles.detail}>{alert.detail}</p>
              </span>
              {alert.to && (
                <span className={styles.go}><ChevronRight size={16} aria-hidden /></span>
              )}
            </>
          );
          const className = `${styles.alert} ${styles[alert.severity]}`;
          return alert.to ? (
            <Link key={alert.id} to={alert.to} className={className}>{inner}</Link>
          ) : (
            <div key={alert.id} className={className}>{inner}</div>
          );
        })
      )}
    </section>
  );
};
