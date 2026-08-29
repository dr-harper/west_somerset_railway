import { useEffect, useState } from 'react';
import { FlaskConical, Info } from 'lucide-react';
import {
  getSettings,
  setSetting,
  subscribe,
  type AdminSettings,
} from '../../services/settings';
import styles from './Admin.module.css';

/**
 * Operator settings.
 *
 * These are testing conveniences, held per-browser rather than in
 * Firestore — switching one on here must never change what a visitor
 * sees on the public site.
 */

interface Toggle {
  key: keyof AdminSettings;
  label: string;
  description: string;
}

const TOGGLES: Toggle[] = [
  {
    key: 'testTrain',
    label: 'Test train',
    description:
      'Adds one synthetic diesel running Minehead to Bishops Lydeard, timed '
      + 'from thirty minutes ago, so Live Trains and the journey tracker can '
      + 'be exercised on a day with no service. It appears only in this '
      + 'browser.',
  },
];

export const AdminSettings: React.FC = () => {
  const [settings, setSettings] = useState(getSettings);

  useEffect(() => subscribe(setSettings), []);

  return (
    <>
      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <h2>Testing</h2>
        </div>

        {TOGGLES.map(toggle => (
          <label key={toggle.key} className={styles.settingRow}>
            <input
              type="checkbox"
              checked={settings[toggle.key]}
              onChange={event => setSetting(toggle.key, event.target.checked)}
            />
            <span>
              <span className={styles.settingLabel}>
                <FlaskConical size={14} aria-hidden />
                {toggle.label}
              </span>
              <span className={styles.muted}>{toggle.description}</span>
            </span>
          </label>
        ))}
      </div>

      <div className={styles.panel}>
        <div className={styles.panelHead}>
          <h2>Not yet configurable</h2>
        </div>
        <p className={styles.muted}>
          <Info size={14} aria-hidden /> The timetable, station list, camera
          registry and detection thresholds are still generated from the
          pipeline and committed to the repository. Changing them means
          re-running{' '}
          <code>python3 camera_registry.py --write</code> or the timetable
          scraper, not editing anything here.
        </p>
      </div>
    </>
  );
};
