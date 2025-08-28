export interface Station {
  id: string;
  name: string;
  code: string;
  coordinates?: {
    lat: number;
    lng: number;
  };
  facilities?: string[];
  isRequestStop?: boolean;
}

export const STATIONS: Station[] = [
  { id: 'BL', name: 'Bishops Lydeard', code: 'BL' },
  { id: 'CH', name: 'Crowcombe Heathfield', code: 'CH' },
  { id: 'STO', name: 'Stogumber', code: 'STO' },
  { id: 'WIL', name: 'Williton', code: 'WIL' },
  { id: 'DON', name: 'Doniford Halt', code: 'DON', isRequestStop: true },
  { id: 'WAT', name: 'Watchet', code: 'WAT' },
  { id: 'WAS', name: 'Washford', code: 'WAS' },
  { id: 'BA', name: 'Blue Anchor', code: 'BA' },
  { id: 'DUN', name: 'Dunster', code: 'DUN' },
  { id: 'MIN', name: 'Minehead', code: 'MIN' }
];