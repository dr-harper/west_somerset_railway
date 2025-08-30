import React, { useEffect } from 'react';
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet';
import L from 'leaflet';
import type { Station, Train } from '../../types/models';
import { getTrackSegments } from '../../data/trackData';
import styles from './TrackMap.module.css';

// Fix for default marker icons in React-Leaflet
import 'leaflet/dist/leaflet.css';

// Fix for missing marker icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

interface TrackMapProps {
  stations: Station[];
  trains?: Train[];
}

// Custom station icon
const createStationIcon = (isTerminal: boolean = false) => {
  return L.divIcon({
    className: 'custom-station-marker',
    html: `
      <div style="
        width: ${isTerminal ? '14px' : '10px'};
        height: ${isTerminal ? '14px' : '10px'};
        background: ${isTerminal ? '#8B4513' : '#2c5530'};
        border: 2px solid white;
        border-radius: 50%;
        box-shadow: 0 2px 4px rgba(0,0,0,0.3);
      "></div>
    `,
    iconSize: [isTerminal ? 18 : 14, isTerminal ? 18 : 14],
    iconAnchor: [isTerminal ? 9 : 7, isTerminal ? 9 : 7],
  });
};

// Custom train icon
const createTrainIcon = (serviceType: string) => {
  const colors = {
    Steam: '#8B4513',
    Diesel: '#2c5530',
    DMU: '#4169E1'
  };
  
  return L.divIcon({
    className: 'custom-train-marker',
    html: `
      <div style="
        width: 20px;
        height: 20px;
        background: ${colors[serviceType as keyof typeof colors] || '#666'};
        border: 3px solid white;
        border-radius: 50%;
        box-shadow: 0 3px 6px rgba(0,0,0,0.4);
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-size: 10px;
        font-weight: bold;
      ">🚂</div>
    `,
    iconSize: [26, 26],
    iconAnchor: [13, 13],
  });
};

// Component to fit bounds after map loads
function FitBounds({ stations }: { stations: Station[] }) {
  const map = useMap();
  
  useEffect(() => {
    if (stations.length > 0) {
      const bounds = L.latLngBounds(
        stations.map(s => [s.coordinates.lat, s.coordinates.lng])
      );
      map.fitBounds(bounds, { padding: [50, 50] });
    }
  }, [map, stations]);
  
  return null;
}

export const TrackMap: React.FC<TrackMapProps> = ({ stations, trains = [] }) => {
  const trackSegments = getTrackSegments();
  
  // Get center point for initial map view
  const centerLat = stations.reduce((sum, s) => sum + s.coordinates.lat, 0) / stations.length || 51.16;
  const centerLng = stations.reduce((sum, s) => sum + s.coordinates.lng, 0) / stations.length || -3.35;
  
  // Find running trains with locations
  const runningTrains = trains.filter(t => 
    t.status.state === 'Running' && t.currentLocation
  );
  
  // Get train positions on the map
  const getTrainPosition = (train: Train): [number, number] | null => {
    if (!train.currentLocation) return null;
    
    if (train.currentLocation.at) {
      const station = stations.find(s => s.code === train.currentLocation!.at);
      return station ? [station.coordinates.lat, station.coordinates.lng] : null;
    }
    
    if (train.currentLocation.between) {
      const [fromCode, toCode] = train.currentLocation.between;
      const fromStation = stations.find(s => s.code === fromCode);
      const toStation = stations.find(s => s.code === toCode);
      
      if (fromStation && toStation) {
        // Interpolate position between stations (simplified - halfway)
        const lat = (fromStation.coordinates.lat + toStation.coordinates.lat) / 2;
        const lng = (fromStation.coordinates.lng + toStation.coordinates.lng) / 2;
        return [lat, lng];
      }
    }
    
    return null;
  };
  
  return (
    <div className={styles.trackMap}>
      <div className={styles.mapHeader}>
        <h3>Track Map</h3>
        <div className={styles.mapLegend}>
          <div className={styles.legendItem}>
            <div className={styles.terminalStation} />
            <span>Terminal Station</span>
          </div>
          <div className={styles.legendItem}>
            <div className={styles.normalStation} />
            <span>Station</span>
          </div>
          {runningTrains.length > 0 && (
            <div className={styles.legendItem}>
              <div className={styles.trainMarker}>🚂</div>
              <span>Train</span>
            </div>
          )}
        </div>
      </div>
      
      <div className={styles.mapContainer}>
        <MapContainer
          center={[centerLat, centerLng]}
          zoom={11}
          className={styles.map}
          scrollWheelZoom={false}
          attributionControl={false}
        >
          <TileLayer
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          
          <FitBounds stations={stations} />
          
          {/* Track segments */}
          {trackSegments.map(segment => (
            <Polyline
              key={segment.id}
              positions={segment.points}
              color="#666"
              weight={3}
              opacity={0.8}
              dashArray={segment.type === 'main' ? undefined : '5, 10'}
            />
          ))}
          
          {/* Station markers */}
          {stations.map(station => {
            const isTerminal = station.code === 'BL' || station.code === 'MIN';
            
            return (
              <Marker
                key={station.code}
                position={[station.coordinates.lat, station.coordinates.lng]}
                icon={createStationIcon(isTerminal)}
              >
                <Popup>
                  <div className={styles.stationPopup}>
                    <h4>{station.name}</h4>
                    <p className={styles.stationCode}>{station.code}</p>
                    {station.facilities && station.facilities.length > 0 && (
                      <div className={styles.facilities}>
                        <strong>Facilities:</strong>
                        <ul>
                          {station.facilities.map((facility, i) => (
                            <li key={i}>{facility}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {station.isRequestStop && (
                      <p className={styles.requestStop}>Request Stop</p>
                    )}
                  </div>
                </Popup>
              </Marker>
            );
          })}
          
          {/* Train markers */}
          {runningTrains.map(train => {
            const position = getTrainPosition(train);
            if (!position) return null;
            
            return (
              <Marker
                key={train.id}
                position={position}
                icon={createTrainIcon(train.serviceType)}
              >
                <Popup>
                  <div className={styles.trainPopup}>
                    <h4>{train.id}</h4>
                    <p>{train.serviceType} Service</p>
                    <p>{train.stops[0].stationName} → {train.stops[train.stops.length - 1].stationName}</p>
                    {train.status.delayMinutes > 0 && (
                      <p className={styles.delay}>Running {train.status.delayMinutes} min late</p>
                    )}
                  </div>
                </Popup>
              </Marker>
            );
          })}
        </MapContainer>
      </div>
    </div>
  );
};