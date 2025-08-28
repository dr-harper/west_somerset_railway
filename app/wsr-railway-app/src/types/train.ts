import type { Station } from './station';

export type ServiceType = 'Diesel' | 'DMU' | 'Steam';
export type ServiceStatus = 'On Time' | 'Delayed' | 'Cancelled';

export interface Train {
  id: string;
  departureTime: string;
  arrivalTime?: string;
  destination: string;
  origin: string;
  serviceType: ServiceType;
  platform?: string;
  status: ServiceStatus;
  delay?: number;
  stops: StopTime[];
}

export interface StopTime {
  station: Station;
  arrivalTime?: string;
  departureTime: string;
  isRequestStop?: boolean;
}

export interface Departure {
  train: Train;
  station: Station;
  scheduledTime: string;
  expectedTime: string;
  platform?: string;
  destination: string;
  serviceType: ServiceType;
  status: ServiceStatus;
}