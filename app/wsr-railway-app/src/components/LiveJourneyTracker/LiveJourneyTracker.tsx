import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import type { Train } from '../../types/models';
import { trainService } from '../../services/trainService';
import styles from './LiveJourneyTracker.module.css';

export const LiveJourneyTracker: React.FC = () => {
  const [activeTrains, setActiveTrains] = useState<Train[]>([]);
  const [upcomingDepartures, setUpcomingDepartures] = useState<Train[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTrains();
    const interval = setInterval(loadTrains, 30000); // Update every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const loadTrains = async () => {
    try {
      const trains = await trainService.getActiveTrains();
      const now = new Date();
      const currentTime = now.toTimeString().slice(0, 5);
      const [currentHour, currentMin] = currentTime.split(':').map(Number);
      const currentMinutes = currentHour * 60 + currentMin;

      // Filter running trains
      const running = trains.filter(t => t.status.state === 'Running');

      // Filter trains departing in next 30 minutes
      const upcoming = trains.filter(t => {
        if (t.status.state !== 'Scheduled') return false;
        const firstDeparture = t.stops[0].scheduledDeparture;
        if (!firstDeparture) return false;

        const [depHour, depMin] = firstDeparture.split(':').map(Number);
        const depMinutes = depHour * 60 + depMin;
        const diffMinutes = depMinutes - currentMinutes;

        // Handle day rollover
        const adjustedDiff = diffMinutes < 0 ? diffMinutes + 1440 : diffMinutes;
        return adjustedDiff > 0 && adjustedDiff <= 30;
      });

      setActiveTrains(running);
      setUpcomingDepartures(upcoming);
    } catch (error) {
      console.error('Failed to load trains:', error);
    } finally {
      setLoading(false);
    }
  };

  const getTrainProgress = (train: Train): { percentage: number; currentStop: string; nextStop: string; currentStopCode: string; nextStopCode: string } => {
    const currentTime = new Date().toTimeString().slice(0, 5);
    let passedStops = 0;
    let currentStop = '';
    let nextStop = '';
    let currentStopCode = '';
    let nextStopCode = '';

    for (let i = 0; i < train.stops.length; i++) {
      const stop = train.stops[i];
      if (stop.scheduledDeparture && currentTime >= stop.scheduledDeparture) {
        passedStops = i + 1;
        currentStop = stop.stationName;
        currentStopCode = stop.stationCode;
      } else if (stop.scheduledArrival && currentTime < stop.scheduledArrival) {
        nextStop = stop.stationName;
        nextStopCode = stop.stationCode;
        break;
      }
    }

    const percentage = (passedStops / train.stops.length) * 100;
    return { percentage, currentStop, nextStop, currentStopCode, nextStopCode };
  };

  const stationOrder = ['MIN', 'DUN', 'BA', 'WAS', 'WAT', 'DON', 'WIL', 'STO', 'CH', 'BL'];

  const getTrainPositionOnLine = (train: Train): number => {
    if (!train.currentLocation) {
      // If no current location, use the first stop
      const firstStopCode = train.stops[0].stationCode;
      const index = stationOrder.indexOf(firstStopCode);
      return (index / (stationOrder.length - 1)) * 100;
    }

    let stationIndex = 0;
    if (train.currentLocation.at) {
      stationIndex = stationOrder.indexOf(train.currentLocation.at);
    } else if (train.currentLocation.between) {
      const [from, to] = train.currentLocation.between;
      const fromIndex = stationOrder.indexOf(from);
      const toIndex = stationOrder.indexOf(to);
      // Place the train between the two stations
      stationIndex = (fromIndex + toIndex) / 2;
    }

    // All trains move along the same line from MIN (left) to BL (right)
    // Position is based on actual location on the track
    return (stationIndex / (stationOrder.length - 1)) * 100;
  };

  const getTimeToNextStop = (train: Train): string => {
    const now = new Date();
    const currentTime = now.toTimeString().slice(0, 5);

    const nextStop = train.stops.find(stop =>
      stop.scheduledArrival && stop.scheduledArrival > currentTime
    );

    if (nextStop && nextStop.scheduledArrival) {
      const [hours, mins] = nextStop.scheduledArrival.split(':').map(Number);
      const [nowHours, nowMins] = currentTime.split(':').map(Number);
      const diffMins = (hours * 60 + mins) - (nowHours * 60 + nowMins);

      if (diffMins < 1) return 'Arriving now';
      if (diffMins === 1) return '1 minute';
      return `${diffMins} minutes`;
    }

    return 'Completing journey';
  };

  const getTimeToDeparture = (train: Train): string => {
    const now = new Date();
    const currentTime = now.toTimeString().slice(0, 5);
    const departure = train.stops[0].scheduledDeparture;

    if (!departure) return '';

    const [hours, mins] = departure.split(':').map(Number);
    const [nowHours, nowMins] = currentTime.split(':').map(Number);
    const diffMins = (hours * 60 + mins) - (nowHours * 60 + nowMins);

    if (diffMins <= 0) return 'Departing now';
    if (diffMins === 1) return '1 minute';
    return `${diffMins} minutes`;
  };

  if (loading) {
    return (
      <div className={styles.tracker}>
        <div className={styles.loading}>Loading train information...</div>
      </div>
    );
  }

  const hasTrains = activeTrains.length > 0 || upcomingDepartures.length > 0;

  if (!hasTrains) {
    return (
      <div className={styles.tracker}>
        <div className={styles.noTrains}>
          <span className={styles.icon}>🚂</span>
          No trains currently running. Services operate from 10:00 to 18:00.
        </div>
      </div>
    );
  }

  return (
    <div className={styles.tracker}>
      <div className={styles.trackerHeader}>
        <h2 className={styles.trackerTitle}>Live Train Status</h2>
        <Link to="/live-trains" className={styles.viewAllLink}>
          View Full Map →
        </Link>
      </div>

      {activeTrains.length > 0 && (
        <div className={styles.section}>
          <div className={styles.trainList}>
            {activeTrains.map(train => {
              const progress = getTrainProgress(train);
              const timeToNext = getTimeToNextStop(train);
              const position = getTrainPositionOnLine(train);

              return (
                <div key={train.id} className={styles.trainCard}>
                  <div className={styles.trainHeader}>
                    <span className={styles.trainId}>{train.id}</span>
                    <span className={`${styles.serviceType} ${styles[train.serviceType.toLowerCase()]}`}>
                      {train.serviceType}
                    </span>
                    <span className={styles.route}>
                      {train.stops[0].stationName} → {train.stops[train.stops.length - 1].stationName}
                    </span>
                  </div>

                  <div className={styles.progressContainer}>
                    <div className={styles.progressBar}>
                      {/* Progress fill based on direction */}
                      {train.origin === 'MIN' ? (
                        // Southbound: MIN to BL (left to right)
                        <div
                          className={styles.progressFill}
                          style={{ width: `${position}%` }}
                        />
                      ) : (
                        // Northbound: BL to MIN (right to left)
                        <div
                          className={styles.progressFill}
                          style={{
                            left: `${position}%`,
                            right: 0,
                            width: `${100 - position}%`
                          }}
                        />
                      )}

                      <div
                        className={`${styles.progressDot} ${train.origin === 'MIN' ? styles.southbound : styles.northbound}`}
                        style={{ left: `${position}%` }}
                      >
                        <span className={styles.arrow}>
                          {train.origin === 'MIN' ? '▶' : '◀'}
                        </span>
                      </div>

                      {/* Station markers */}
                      {stationOrder.map((code, index) => (
                        <div
                          key={code}
                          className={styles.stationMarker}
                          style={{ left: `${(index / (stationOrder.length - 1)) * 100}%` }}
                        >
                          <div className={styles.stationTick} />
                          <span className={styles.stationCode}>{code}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className={styles.trainStatus}>
                    {train.currentLocation?.between ? (
                      <span>Between {progress.currentStop} and {progress.nextStop}</span>
                    ) : train.currentLocation?.at ? (
                      <span>At {progress.currentStop}</span>
                    ) : (
                      <span>Next stop: {progress.nextStop}</span>
                    )}
                    <span className={styles.timeToNext}>in {timeToNext}</span>
                  </div>

                  {train.status.delayMinutes > 0 && (
                    <div className={styles.delay}>
                      Running {train.status.delayMinutes} minutes late
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {upcomingDepartures.length > 0 && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>Departing Soon</h3>
          <div className={styles.upcomingList}>
            {upcomingDepartures.map(train => (
              <div key={train.id} className={styles.upcomingCard}>
                <div className={styles.upcomingInfo}>
                  <span className={styles.trainId}>{train.id}</span>
                  <span className={`${styles.serviceType} ${styles[train.serviceType.toLowerCase()]}`}>
                    {train.serviceType}
                  </span>
                  <span className={styles.route}>
                    {train.stops[0].stationName} → {train.stops[train.stops.length - 1].stationName}
                  </span>
                </div>
                <div className={styles.departureTime}>
                  <span className={styles.time}>{train.stops[0].scheduledDeparture}</span>
                  <span className={styles.countdown}>
                    Leaving {train.stops[0].stationName} in {getTimeToDeparture(train)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};