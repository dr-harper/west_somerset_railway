import { useState, useEffect } from 'react';
import { ServiceCalendar } from '../../components/ServiceCalendar/ServiceCalendar';
import { StationSelector } from '../../components/StationSelector/StationSelector';
import { trainService } from '../../services/trainService';
import type { Station, Train } from '../../types/models';
import styles from './JourneyPlanner.module.css';
import { getTrainsForDate } from '../../services/timetables';

export const JourneyPlanner: React.FC = () => {
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [fromStation, setFromStation] = useState<Station | null>(null);
  const [toStation, setToStation] = useState<Station | null>(null);
  const [stations, setStations] = useState<Station[]>([]);
  const [, setLoading] = useState(true);
  const [searchResults, setSearchResults] = useState<Train[]>([]);
  const [searching, setSearching] = useState(false);
  const [currentViewMonth, setCurrentViewMonth] = useState<Date>(new Date());

  async function loadStations() {
    try {
      const allStations = await trainService.getAllStations();
      setStations(allStations);
    } catch (error) {
      console.error('Failed to load stations:', error);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStations();
  }, []);

  const handleDateSelection = (date: Date) => {
    setSelectedDate(date);
    trainService.setServiceDate(date);
  };

  const handleSwapStations = () => {
    const temp = fromStation;
    setFromStation(toStation);
    setToStation(temp);
  };

  const canPlanJourney = fromStation && toStation && fromStation.code !== toStation.code;

  const handlePlanJourney = async () => {
    if (!canPlanJourney || !fromStation || !toStation) return;
    
    setSearching(true);
    setSearchResults([]);
    
    try {
      // Get all trains for the selected date
      const trains = getTrainsForDate(selectedDate);
      
      // Filter trains that go from fromStation to toStation
      const matchingTrains = trains.filter(train => {
        const fromIndex = train.stops.findIndex(stop => stop.stationCode === fromStation.code);
        const toIndex = train.stops.findIndex(stop => stop.stationCode === toStation.code);
        
        // Check if both stations exist and are in the right order
        return fromIndex !== -1 && toIndex !== -1 && fromIndex < toIndex;
      });
      
      setSearchResults(matchingTrains);
    } catch (error) {
      console.error('Failed to search for journeys:', error);
    } finally {
      setSearching(false);
    }
  };

  return (
    <div className="container">
      <div className="contentWrapper">
        <div className={styles.pageHeader}>
          <h1 className={styles.title}>Journey Planner</h1>
          <p className={styles.subtitle}>
            Plan your journey on the West Somerset Railway
          </p>
        </div>

        {/* Calendar Section */}
        <div className={styles.calendarSection}>
          <ServiceCalendar 
            selectedDate={selectedDate}
            onDateSelect={handleDateSelection}
            currentViewMonth={currentViewMonth}
            onMonthChange={setCurrentViewMonth}
          />
        </div>

        {/* Journey Planning Section */}
        <div className={styles.journeySection}>
          <h2 className={styles.sectionTitle}>Plan Your Journey</h2>
          
          <div className={styles.stationSelectors}>
            <div className={styles.stationGroup}>
              <label className={styles.label}>From</label>
              <StationSelector
                stations={stations}
                selectedStation={fromStation}
                onStationChange={setFromStation}
                placeholder="Select departure station"
              />
            </div>

            <button 
              className={styles.swapButton}
              onClick={handleSwapStations}
              aria-label="Swap stations"
              title="Swap stations"
            >
              ⇄
            </button>

            <div className={styles.stationGroup}>
              <label className={styles.label}>To</label>
              <StationSelector
                stations={stations}
                selectedStation={toStation}
                onStationChange={setToStation}
                placeholder="Select arrival station"
              />
            </div>
          </div>

          <div className={styles.selectedDateInfo}>
            <span className={styles.dateLabel}>Travel Date:</span>
            <span className={styles.dateValue}>
              {selectedDate.toLocaleDateString('en-GB', { 
                weekday: 'long', 
                day: 'numeric', 
                month: 'long',
                year: 'numeric'
              })}
            </span>
          </div>

          <button 
            className={styles.planButton}
            onClick={handlePlanJourney}
            disabled={!canPlanJourney || searching}
          >
            {searching ? 'Searching...' : 'Find Trains'}
          </button>

          {fromStation && toStation && fromStation.code === toStation.code && (
            <div className={styles.warning}>
              Please select different stations for your journey
            </div>
          )}
        </div>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className={styles.resultsSection}>
            <h2 className={styles.sectionTitle}>Available Trains</h2>
            <div className={styles.resultsList}>
              {searchResults.map((train) => {
                const fromStop = train.stops.find(s => s.stationCode === fromStation?.code);
                const toStop = train.stops.find(s => s.stationCode === toStation?.code);
                
                if (!fromStop || !toStop) return null;
                
                return (
                  <div key={train.id} className={styles.resultCard}>
                    <div className={styles.resultHeader}>
                      <span className={styles.serviceType}>{train.serviceType}</span>
                      <span className={styles.trainId}>Service {train.id}</span>
                    </div>
                    <div className={styles.resultBody}>
                      <div className={styles.departureInfo}>
                        <div className={styles.stationName}>{fromStation?.name}</div>
                        <div className={styles.time}>{fromStop.scheduledDeparture || fromStop.scheduledArrival}</div>
                      </div>
                      <div className={styles.arrow}>→</div>
                      <div className={styles.arrivalInfo}>
                        <div className={styles.stationName}>{toStation?.name}</div>
                        <div className={styles.time}>{toStop.scheduledArrival || toStop.scheduledDeparture}</div>
                      </div>
                    </div>
                    {train.notes && (
                      <div className={styles.notes}>{train.notes}</div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {searchResults.length === 0 && !searching && fromStation && toStation && (
          <div className={styles.noResults}>
            <p>No direct trains found for this journey.</p>
            <p>Try selecting different stations or check the timetable for this date.</p>
          </div>
        )}
      </div>
    </div>
  );
};