// The camera list, generated from the detection pipeline.
//
// Three pages used to keep their own hardcoded copy, all six entries long
// and all stale once five more cameras were added — detections from the
// newer ones showed as raw ids like `williton_2` and were missing from the
// per-camera counts entirely. Regenerate with:
//
//   python3 train_detection/camera_registry.py --write

import cameraData from '../data/cameras.json';

export interface CameraAnnotation {
  roads: number;
  platforms: number;
  occluders: number;
  blockedShare: number;
  orientationKnown: boolean;
  ready: boolean;
}

export interface Camera {
  id: string;
  name: string;
  station: string | null;
  stationName: string | null;
  lineIndex: number | null;
  videoId: string;
  directionValidated: boolean;
  annotation: CameraAnnotation;
}

/** Ordered along the line, Bishops Lydeard end first. */
export const CAMERAS: Camera[] = cameraData as Camera[];

const BY_ID = new Map(CAMERAS.map(camera => [camera.id, camera]));

export function getCamera(id: string): Camera | undefined {
  return BY_ID.get(id);
}

/**
 * A camera's display name, falling back to the raw id.
 *
 * The fallback matters: an episode can arrive from a camera added to the
 * pipeline but not yet regenerated here, and showing `williton_2` is far
 * better than showing nothing.
 */
export function cameraName(id: string): string {
  return BY_ID.get(id)?.name ?? id;
}

/** Cameras that have appeared in the data but are not in the registry. */
export function unknownCameras(ids: Iterable<string>): string[] {
  return [...new Set(ids)].filter(id => !BY_ID.has(id)).sort();
}
