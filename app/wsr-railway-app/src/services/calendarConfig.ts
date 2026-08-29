// West Somerset Railway calendar configuration
// Driven by real data scraped from the official WSR calendar
// (see route_data/timetable_2026/build_app_data.py)

import timetableData from '../data/timetable2026.json';

export type TimetableType =
  | 'red' | 'blue' | 'orange' | 'yellow' | 'brown'
  | 'purple' | 'green' | 'none';

export type DayKind = 'service' | 'event' | 'closed' | 'unknown';

export interface DayInfo {
  kind: DayKind;
  family: TimetableType;
  patternId?: string;
  patternTitle?: string;
  events?: string[];
  pdf?: string;
}

interface RawStop {
  c: string;
  a: string | null;
  d: string | null;
  x?: boolean;
  p?: string;
}

export interface RawService {
  direction: 'NB' | 'SB';
  serviceType: 'Steam' | 'Diesel' | 'DMU';
  loco: string | null;
  stops: RawStop[];
}

interface RawPattern {
  family: string;
  title: string;
  services: RawService[];
}

interface RawDay {
  kind: string;
  pattern?: string;
  family?: string;
  events?: string[];
  pdf?: string;
}

const patterns = timetableData.patterns as unknown as Record<string, RawPattern>;
const rawDays = timetableData.days as unknown as Record<string, RawDay>;

// Format a date as YYYY-MM-DD in local time (toISOString would shift the
// day at BST midnight)
export function toDateKey(date: Date): string {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
}

export function getDayInfo(date: Date): DayInfo {
  const raw = rawDays[toDateKey(date)];
  if (!raw) {
    return { kind: 'unknown', family: 'none' };
  }
  if (raw.kind === 'service' && raw.pattern) {
    const pattern = patterns[raw.pattern];
    return {
      kind: 'service',
      family: (pattern.family as TimetableType) ?? 'none',
      patternId: raw.pattern,
      patternTitle: pattern.title,
      pdf: raw.pdf
    };
  }
  if (raw.kind === 'event') {
    return {
      kind: 'event',
      family: (raw.family as TimetableType) ?? 'green',
      events: raw.events ?? []
    };
  }
  return { kind: 'closed', family: 'none' };
}

// Date -> timetable family, for calendar colouring
export const serviceCalendar: Record<string, TimetableType> = Object.fromEntries(
  Object.entries(rawDays).map(([date, raw]) => {
    if (raw.kind === 'service' && raw.pattern) {
      return [date, patterns[raw.pattern].family as TimetableType];
    }
    if (raw.kind === 'event') {
      return [date, (raw.family as TimetableType) ?? 'green'];
    }
    return [date, 'none'];
  })
);

// Date -> special event / named timetable, for calendar labels
export const specialEvents: Record<string, string> = Object.fromEntries(
  Object.entries(rawDays).flatMap(([date, raw]) => {
    if (raw.kind === 'service' && raw.pattern) {
      const pattern = patterns[raw.pattern];
      if (pattern.family === 'purple') {
        return [[date, pattern.title]];
      }
      return [];
    }
    if (raw.kind === 'event' && raw.events && raw.events.length > 0) {
      return [[date, raw.events.join(' • ')]];
    }
    return [];
  })
);

export function getTimetableType(date: Date): TimetableType {
  return serviceCalendar[toDateKey(date)] ?? 'none';
}

export function hasServices(date: Date): boolean {
  return getDayInfo(date).kind === 'service';
}

export function getSpecialEvent(date: Date): string | undefined {
  return specialEvents[toDateKey(date)];
}

export function getDatesWithTimetable(timetableType: TimetableType): string[] {
  return Object.entries(serviceCalendar)
    .filter(([, type]) => type === timetableType)
    .map(([date]) => date);
}

// The most-used pattern of each family, for schedule previews
export function getRepresentativePattern(family: TimetableType): { id: string; pattern: RawPattern } | null {
  const usage: Record<string, number> = {};
  for (const raw of Object.values(rawDays)) {
    if (raw.kind === 'service' && raw.pattern) {
      usage[raw.pattern] = (usage[raw.pattern] ?? 0) + 1;
    }
  }
  const candidates = Object.entries(patterns)
    .filter(([, p]) => p.family === family)
    .sort(([a], [b]) => (usage[b] ?? 0) - (usage[a] ?? 0));
  if (candidates.length === 0) return null;
  const [id, pattern] = candidates[0];
  return { id, pattern };
}

// Colours matching the official WSR calendar
export const timetableColors: Record<TimetableType, string> = {
  red: '#B92E2A',
  blue: '#3D75ED',
  orange: '#F07D0A',
  yellow: '#E0CF3C',
  brown: '#895129',
  purple: '#9A06F9',
  green: '#48731D',
  none: '#DEDBDB'
};

export const timetableNames: Record<TimetableType, string> = {
  red: 'Red Timetable',
  blue: 'Blue Timetable',
  orange: 'Orange Timetable',
  yellow: 'Yellow Timetable',
  brown: 'Brown Timetable',
  purple: 'Special Event',
  green: 'Christmas Services',
  none: 'No Services'
};

function describePattern(pattern: RawPattern): string {
  const nb = pattern.services.filter(s => s.direction === 'NB');
  const counts: Record<string, number> = {};
  for (const s of nb) {
    counts[s.serviceType] = (counts[s.serviceType] ?? 0) + 1;
  }
  const mix = ['Steam', 'Diesel', 'DMU']
    .filter(t => counts[t])
    .map(t => `${counts[t]} ${t}`)
    .join(', ');
  const first = nb
    .map(s => s.stops[0]?.d)
    .filter(Boolean)
    .sort()[0];
  const parts = [`${nb.length} trains each way`, mix];
  if (first) parts.push(`first departure ${first}`);
  return parts.join(' • ');
}

// Summaries computed from the real timetable data
export const timetableSummaries: Record<TimetableType, string> = {
  red: '', blue: '', orange: '', yellow: '', brown: '',
  purple: 'Special event timetable • Intensive service • Check the day for details',
  green: 'Festive services • Pre-booked events such as the Santa Express',
  none: 'No scheduled services'
};

for (const family of ['red', 'blue', 'orange', 'yellow', 'brown'] as const) {
  const rep = getRepresentativePattern(family);
  timetableSummaries[family] = rep
    ? describePattern(rep.pattern)
    : 'No scheduled services';
}
