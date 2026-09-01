/**
 * The hand-drawn knowledge about each camera: where the rails run, which
 * parts of the picture are platform or obstruction, which end is Minehead.
 *
 * This is the file the detection pipeline reads on its next run, so a bad
 * write here un-annotates the railway. Loading and saving are kept in one
 * place, apart from the drawing, so that the risky half is small enough to
 * read in one go.
 */

/** Everything is traced in the frame the watcher works in. */
export const FRAME_WIDTH = 854;
export const FRAME_HEIGHT = 480;

export type Point = [number, number];
export type TrackKind = 'running' | 'loop' | 'siding' | 'shed';
export type RegionKind = 'platform' | 'occluder';

export interface Track {
  name: string;
  kind: TrackKind;
  rails: { a: Point[]; b: Point[] };
}

export interface Region {
  name: string;
  kind: RegionKind;
  points: Point[];
}

export interface MaskCells {
  grid: [number, number];
  cells: number[];
}

export interface CameraTrace {
  tracks: Track[];
  anchors: unknown[];
  regions: Region[];
  mask_cells?: MaskCells;
  /** Which end of the traced line points towards Minehead. */
  minehead_end?: 'start' | 'end';
}

export type TraceFile = Record<string, CameraTrace>;

const ENDPOINT = '/api/camera-tracks';

export async function loadTraces(): Promise<TraceFile> {
  const response = await fetch(ENDPOINT, { cache: 'no-store' });
  if (!response.ok) throw new Error(`Could not read annotations (${response.status})`);
  const data = await response.json();
  const out: TraceFile = {};
  for (const [camera, trace] of Object.entries(data)) {
    if (camera.startsWith('_')) continue;      // the file's own note
    out[camera] = normalise(trace as Partial<CameraTrace>);
  }
  return out;
}

/** Fill in what an older or partial entry leaves out. */
export function normalise(trace: Partial<CameraTrace>): CameraTrace {
  return {
    tracks: (trace.tracks ?? []).map(t => ({
      name: t.name ?? 'running line',
      kind: t.kind ?? 'running',
      rails: { a: t.rails?.a ?? [], b: t.rails?.b ?? [] },
    })),
    anchors: trace.anchors ?? [],
    regions: (trace.regions ?? []).map(r => ({
      name: r.name ?? r.kind ?? 'platform',
      kind: r.kind ?? 'platform',
      points: r.points ?? [],
    })),
    mask_cells: trace.mask_cells,
    minehead_end: trace.minehead_end,
  };
}

export async function saveTraces(traces: TraceFile): Promise<number> {
  if (!Object.keys(traces).length) {
    // The endpoint refuses this too, but failing here means a bug in the
    // page cannot even reach the file.
    throw new Error('Refusing to save annotations for no cameras');
  }
  const response = await fetch(ENDPOINT, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(traces),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error ?? `Save failed (${response.status})`);
  return body.cameras ?? 0;
}

/** Whether a camera has enough traced for the pipeline to use it. */
export function isReady(trace: CameraTrace): boolean {
  return trace.tracks.some(t => t.rails.a.length >= 2 && t.rails.b.length >= 2);
}

export function countPoints(trace: CameraTrace): number {
  const rails = trace.tracks.reduce(
    (n, t) => n + t.rails.a.length + t.rails.b.length, 0);
  const regions = trace.regions.reduce((n, r) => n + r.points.length, 0);
  return rails + regions;
}
