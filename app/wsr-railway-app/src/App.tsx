import { useState, useEffect } from 'react';
import './styles/global.css';
import './App.css';
import { Header } from './components/Layout/Header';
import { Footer } from './components/Layout/Footer';
import { DepartureBoard } from './components/DepartureBoard/DepartureBoard';
import { StationSelector } from './components/StationSelector/StationSelector';
import { DatePicker } from './components/DatePicker/DatePicker';
import { STATIONS } from './types/station';
import type { Station } from './types/station';
import type { Departure } from './types/train';
import { getNextDepartures } from './services/departureService';

function App() {
  const [selectedStation, setSelectedStation] = useState<Station | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [departures, setDepartures] = useState<Departure[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (selectedStation) {
      setLoading(true);
      // Simulate API call delay
      setTimeout(() => {
        const deps = getNextDepartures(selectedStation, selectedDate, 10);
        setDepartures(deps);
        setLoading(false);
      }, 300);
    }
  }, [selectedStation, selectedDate]);

  return (
    <div className="app">
      <Header />
      
      <main className="main">
        <div className="container">
          <div className="contentWrapper">
            <div className="controls">
            <StationSelector
              stations={STATIONS}
              selectedStation={selectedStation}
              onStationChange={setSelectedStation}
            />
            <DatePicker
              selectedDate={selectedDate}
              onDateChange={setSelectedDate}
            />
            </div>

            <div className="departureSection">
              {loading ? (
                <div className="loadingContainer">
                  <div className="loading">Loading departures...</div>
                </div>
              ) : selectedStation ? (
                <DepartureBoard
                  station={selectedStation}
                  departures={departures}
                />
              ) : (
                <div className="loadingContainer">
                  <div className="loading">Please select a station to view departures</div>
                </div>
              )}
            </div>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}

export default App;