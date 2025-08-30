// Track data configuration - easily replaceable with actual track coordinates
// Currently using straight lines between stations as placeholders

import type { LatLngExpression } from 'leaflet';

export interface TrackSegment {
  id: string;
  points: LatLngExpression[];
  type: 'main' | 'siding' | 'platform';
}

// Placeholder track data - replace this with actual track coordinates when available
// For now, this creates straight lines between stations
export const getTrackSegments = (): TrackSegment[] => {
  // Station coordinates in order from Bishops Lydeard to Minehead
  // Using actual coordinates from mockStations
  const stationCoords: LatLngExpression[] = [
    [51.05526555357071, -3.1939831447400424], // BL - Bishops Lydeard
    [51.102683806851786, -3.2338928074524973], // CH - Crowcombe Heathfield
    [51.12791469181247, -3.2733470229230224], // STO - Stogumber
    [51.166215218812056, -3.309489866648678], // WIL - Williton
    [51.17841737732154, -3.3113258133497485], // DON - Doniford Halt
    [51.18083509803016, -3.329631778829393], // WAT - Watchet
    [51.16169572799292, -3.368545896756289], // WAS - Washford
    [51.18177271081976, -3.4012355263416287], // BA - Blue Anchor
    [51.1931315884899, -3.4385530693148945], // DUN - Dunster
    [51.206815, -3.4711559], // MIN - Minehead
  ];

  // Create main track segments between stations
  const segments: TrackSegment[] = [];
  
  for (let i = 0; i < stationCoords.length - 1; i++) {
    segments.push({
      id: `main-track-${i}`,
      points: [stationCoords[i], stationCoords[i + 1]],
      type: 'main'
    });
  }

  return segments;
};

// Future implementation example:
// export const getTrackSegments = (): TrackSegment[] => {
//   return [
//     {
//       id: 'bl-ch-main',
//       points: [
//         [51.0542, -3.0744],
//         [51.0601, -3.0812],
//         [51.0652, -3.0889],
//         // ... more detailed track points
//         [51.0792, -3.1028]
//       ],
//       type: 'main'
//     },
//     // ... more segments
//   ];
// };