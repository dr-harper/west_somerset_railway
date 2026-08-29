// Where detection stills are served from.
//
// These were built as root-absolute `/captures/...`, which resolves only
// when the app is served from the domain root. On GitHub Pages the base is
// /west_somerset_railway/, so every keyframe 404'd there while working
// perfectly in local dev — the worst kind of bug to leave in an operator
// tool, because the page still renders and simply shows nothing.

const BASE = import.meta.env.BASE_URL.replace(/\/$/, '');

export function captureUrl(filename: string | null | undefined): string | null {
  if (!filename) return null;
  return `${BASE}/captures/${filename}`;
}
