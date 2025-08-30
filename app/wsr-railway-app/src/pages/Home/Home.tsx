import { useState, useEffect } from 'react';
import { DepartureBoard } from '../../components/DepartureBoard/DepartureBoard';
import { StationSelector } from '../../components/StationSelector/StationSelector';
import { DatePicker } from '../../components/DatePicker/DatePicker';
import { LiveJourneyTracker } from '../../components/LiveJourneyTracker/LiveJourneyTracker';
import type { Station, StationCode } from '../../types/models';
import { trainService } from '../../services/trainService';

export const Home: React.FC = () => {
  const [selectedStationCode, setSelectedStationCode] = useState<StationCode | null>(null);
  const [selectedStation, setSelectedStation] = useState<Station | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStations();
  }, []);

  useEffect(() => {
    if (selectedStationCode) {
      const station = stations.find(s => s.code === selectedStationCode);
      setSelectedStation(station || null);
    }
  }, [selectedStationCode, stations]);

  const loadStations = async () => {
    try {
      const allStations = await trainService.getAllStations();
      setStations(allStations);
    } catch (error) {
      console.error('Failed to load stations:', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="contentWrapper">
        <LiveJourneyTracker />
        <div className="controls">
          <StationSelector
            stations={stations}
            selectedStation={selectedStation}
            onStationChange={(station) => {
              setSelectedStation(station);
              setSelectedStationCode(station?.code || null);
            }}
          />
          <DatePicker
            selectedDate={selectedDate}
            onDateChange={setSelectedDate}
          />
        </div>

        <div className="departureSection">
          {loading ? (
            <div className="loadingContainer">
              <div className="loading">Loading stations...</div>
            </div>
          ) : (
            <DepartureBoard
              stationCode={selectedStationCode}
              stationName={selectedStation?.name}
            />
          )}
        </div>
      </div>
    </div>
  );
};