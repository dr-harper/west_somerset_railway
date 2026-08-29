import { CalendarDays, Flag } from 'lucide-react';
import { useState, useEffect } from 'react';
import { DepartureBoard } from '../../components/DepartureBoard/DepartureBoard';
import { StationSelector } from '../../components/StationSelector/StationSelector';
import { DatePicker } from '../../components/DatePicker/DatePicker';
import { LiveJourneyTracker } from '../../components/LiveJourneyTracker/LiveJourneyTracker';
import type { Station, StationCode } from '../../types/models';
import { trainService } from '../../services/trainService';
import type { TimetableType } from '../../services/calendarConfig';

export const Home: React.FC = () => {
  const [selectedStationCode, setSelectedStationCode] = useState<StationCode | null>(null);
  const [selectedStation, setSelectedStation] = useState<Station | null>(null);
  const [selectedDate, setSelectedDate] = useState<Date>(new Date());
  const [stations, setStations] = useState<Station[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasServicesToday, setHasServicesToday] = useState(true);
  const [timetableInfo, setTimetableInfo] = useState<{
    type: TimetableType;
    kind?: string;
    name: string;
    color: string;
    summary: string;
    specialEvent?: string;
  } | null>(null);

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

  async function checkActiveServices() {
    try {
      const trains = await trainService.getActiveTrains();
      
      // Get timetable information
      const info = await trainService.getTimetableInfo();
      setTimetableInfo(info);
      
      // Check if there are any services today
      const now = new Date();
      const currentTime = now.toTimeString().slice(0, 5);
      const hour = parseInt(currentTime.split(':')[0]);
      
      // Check if we have any scheduled or running trains
      const hasActiveServices = trains.some(train => 
        train.status.state === 'Running' || train.status.state === 'Scheduled'
      );
      
      // If timetable type is 'none' or it's late in the day with no services
      const isEndOfDay = hour >= 18;
      setHasServicesToday(info.type !== 'none' && (hasActiveServices || !isEndOfDay));
      
    } catch (error) {
      console.error('Failed to check active services:', error);
    }
  }

  useEffect(() => {
    loadStations();
    checkActiveServices();
  }, []);

  useEffect(() => {
    if (selectedStationCode) {
      const station = stations.find(s => s.code === selectedStationCode);
      setSelectedStation(station || null);
    }
  }, [selectedStationCode, stations]);

  const handleDateSelection = (date: Date) => {
    setSelectedDate(date);
    trainService.setServiceDate(date);
    checkActiveServices();
  };

  return (
    <div className="container">
      <div className="contentWrapper">
        {timetableInfo && timetableInfo.type !== 'none' && (
          <div style={{
            backgroundColor: timetableInfo.color + '20',
            border: `2px solid ${timetableInfo.color}`,
            borderRadius: '8px',
            padding: '12px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '12px',
                height: '12px',
                borderRadius: '50%',
                backgroundColor: timetableInfo.color
              }} />
              <div>
                <strong style={{ color: timetableInfo.color }}>
                  {timetableInfo.name}
                </strong>
                <p style={{ margin: '2px 0 0 0', fontSize: '13px', color: 'var(--ink-soft)' }}>
                  {timetableInfo.summary}
                </p>
                {timetableInfo.specialEvent && (
                  <p style={{ margin: '2px 0 0 0', fontSize: '13px', fontStyle: 'italic', color: 'var(--ink-soft)' }}>
                    {timetableInfo.specialEvent}
                  </p>
                )}
              </div>
            </div>
            <div style={{ fontSize: '14px', color: 'var(--ink-soft)' }}>
              {new Date().toLocaleDateString('en-GB', { 
                weekday: 'long', 
                day: 'numeric', 
                month: 'long' 
              })}
            </div>
          </div>
        )}
        {timetableInfo?.kind === 'unknown' && (
          <div style={{
            backgroundColor: 'var(--paper-raised)',
            border: '1px solid var(--rule)',
            borderLeft: '4px solid var(--brass)',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <CalendarDays size={24} aria-hidden />
            <div>
              <strong style={{ color: 'var(--chocolate)', fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Timetable Not Yet Published</strong>
              <p style={{ margin: '4px 0 0 0', color: 'var(--ink-soft)' }}>
                The railway has not yet released its timetable for this date.
                Please check nearer the time.
              </p>
            </div>
          </div>
        )}
        {timetableInfo?.kind !== 'unknown' && !hasServicesToday && (
          <div style={{
            backgroundColor: 'var(--paper-raised)',
            border: '1px solid var(--rule)',
            borderLeft: '4px solid var(--signal-red)',
            borderRadius: '8px',
            padding: '16px',
            marginBottom: '20px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px'
          }}>
            <Flag size={24} aria-hidden />
            <div>
              <strong style={{ color: 'var(--signal-red)', fontFamily: 'var(--font-display)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>No Services Running Today</strong>
              <p style={{ margin: '4px 0 0 0', color: 'var(--ink-soft)' }}>
                There are no trains scheduled for the remainder of today. 
                Please check tomorrow's timetable for upcoming services.
              </p>
            </div>
          </div>
        )}
        
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
            onDateChange={handleDateSelection}
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