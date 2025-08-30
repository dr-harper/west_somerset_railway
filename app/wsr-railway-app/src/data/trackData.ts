// Track data configuration with real West Somerset Railway track coordinates
import type { LatLngExpression } from 'leaflet';
import segmentsDataRaw from './segments.geojson?raw';

const segmentsData = JSON.parse(segmentsDataRaw);

// Type definitions for the GeoJSON data
interface GeoJSONFeature {
  type: 'Feature';
  geometry: {
    type: 'LineString';
    coordinates: number[][];
  };
  properties: {
    from: string;
    to: string;
    length_m_approx: number;
  };
}

interface GeoJSONData {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

export interface TrackSegment {
  id: string;
  points: LatLngExpression[];
  type: 'main' | 'siding' | 'platform';
  from?: string;
  to?: string;
  length_m?: number;
}

// Convert GeoJSON coordinates [lng, lat] to Leaflet format [lat, lng]
const convertCoordinates = (coords: number[][]): LatLngExpression[] => {
  return coords.map(coord => [coord[1], coord[0]] as LatLngExpression);
};

// Get track segments from real GeoJSON data
export const getTrackSegments = (): TrackSegment[] => {
  const segments: TrackSegment[] = [];
  
  // Process each feature from the GeoJSON
  (segmentsData as GeoJSONData).features.forEach((feature, index) => {
    const { geometry, properties } = feature;
    
    // Convert coordinates from GeoJSON format to Leaflet format
    const points = convertCoordinates(geometry.coordinates);
    
    // Create segment ID from station names or use index
    const id = properties.from && properties.to 
      ? `${properties.from.toLowerCase().replace(/\s+/g, '-')}-to-${properties.to.toLowerCase().replace(/\s+/g, '-')}`
      : `segment-${index}`;
    
    segments.push({
      id,
      points,
      type: 'main',
      from: properties.from,
      to: properties.to,
      length_m: properties.length_m_approx
    });
  });
  
  return segments;
};