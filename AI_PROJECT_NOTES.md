# West Somerset Railway — project notes

Personal project: a timetable web app and a live train-detection system for
the West Somerset Railway (heritage line, Bishops Lydeard → Minehead,
ex-GWR). Updated 29th August 2026.

## Layout

```
app/wsr-railway-app/      React 19 + Vite + TS web app (real 2026 timetable)
route_data/               Overpass route data + timetable_2026/ scrape & transform
train_detection/          live webcam detection system (YOLO11 + zones)
```

## Web app (`app/wsr-railway-app`)

- **Data source of truth**: `src/data/timetable2026.json` — GENERATED, do not
  hand-edit. Regenerate with `route_data/timetable_2026/build_app_data.py`
  from the raw scrape JSONs in the same folder (scraped from the official
  WSR calendar page, where each day's modal contains full timetable tables).
- `services/calendarConfig.ts` — day classification (8 timetable families:
  red/blue/orange/yellow/brown/purple/green/none), colours from the official
  site, summaries computed from the data. Use `toDateKey()` for date keys
  (local time — `toISOString()` shifts days under BST).
- `services/timetables.ts` — builds `Train` objects per date;
  `getFamilySchedules()` drives the schedule preview components.
- **Theme**: "GWR print room" — cream paper / chocolate / brass tokens in
  `styles/variables.css`, Oswald + Cabin fonts. Signature: split-flap
  departure board (`DepartureBoard`), Edmondson ticket journey results,
  signal-box style route diagram.
- Tests: `npm test` (vitest). Lint and `tsc -b` are clean — keep them so.
- Train positions are still SIMULATED from the schedule; wiring real
  detection events in is the next milestone.

## Timetable scrape (`route_data/timetable_2026`)

- Cell notation handled by the parser: `10x28` = calls & trains cross,
  `08//32` = passes non-stop (not a call), `-`/STOP/START = short workings,
  duplicate station rows = arrive/depart pairs.
- `TITLE_OVERRIDES` renames the site's "12.08 - Timetable 2026" oddity.
  Family matching uses word boundaries ("(Reduced)" must not match "red").
- Christmas (green) days have no public timetable yet — re-scrape when the
  WSR publishes it (late 2026). 2027 season: not yet published.
- Tests: `pytest test_build_app_data.py`.

## Train detection (`train_detection`)

- Six public Railcam webcams via YouTube Live HLS (`wsr_live_capture.py`).
  Streams offer up to 1080p; the pipeline runs at 854×480.
- `detection_zones.py`: per-camera polygons (detect/approach/ignore),
  calibrated at 854×480 — recalibrate if a camera is repositioned.
- `gala_watcher.py`: two-tier watcher (motion gate → YOLO11 episodes).
  Idle cost ~7% of one core. Episodes → `episodes.jsonl`, media →
  `captures/` (gitignored).
- `episode_analysis.py`: episodes ↔ timetable matching (superseded for
  tracking by the modules below, still used for single-sighting queries).
- `train_tracker.py`: the line graph — stations as nodes, real geojson
  segments as edges — plus position interpolation in the app's
  TrainLocation shape.
- `movement_tracker.py`: the primary tracker. Chains sightings into
  physical movements using transit windows, direction and optional
  identity, THEN compares to the timetable. An unmatched movement is an
  unscheduled working, tracked in full. Prefer this over train_tracker's
  run assignment.
- `upload_episodes.py` + the app's `/verify` page: the human verification
  loop, backed by Firestore.
- `classify_trains.py`: per-episode Gemini classification (structured
  output). Needs a fresh key.
- `track_geometry.py` + `track_annotator.html`: per-camera track geometry.
  A camera usually sees SEVERAL roads (Blue Anchor is a passing loop,
  Minehead has shed roads and sidings, the Seaward Crossing has a goods
  siding), so each is traced separately with its own name and kind
  (running / loop / siding / shed). `project()` attributes a detection to
  the road it stands on, comparing offsets in gauges rather than pixels so
  a distant siding is not unfairly favoured, and flags the attribution
  ambiguous when two roads fit almost equally. Only running lines and
  loops carry timetabled movements; stock on the rest is stabled.
  Each road is a PAIR of multi-point rails rather than one line. Two rails
  are what make perspective recoverable: their real separation is a known
  1.435 m, so the pixel gap between them gives metres-per-pixel at every
  depth. From that comes direction (local tangent), position along the
  track (arc length), and speed in mph from a single camera. Trace with
  `python3 serve_annotator.py --lan`, which prints a phone-reachable URL
  (tracing rails by touch is far easier than by trackpad — there is a
  magnifier under the finger for precision). Do rail A and rail B for
  each camera; traces live in
  `camera_tracks.json` (854x480 image space, each rail ordered from the
  Bishops Lydeard end towards Minehead). NOTHING IS TRACED YET — tracing
  accurately needs a finger on the photograph; doing it by computed
  coordinates put the lines on the platform instead of the rails.

### Findings from the 29th August gala (the only full day of real data)

- Direction vectors validated 100% at Bishops Lydeard, Blue Anchor,
  Crowcombe and Minehead. Watchet is in `UNRELIABLE_DRIFT_CAMERAS`: it
  looks along a curve, so northbound drifts left while southbound drifts
  down and no single vector separates them — direction there comes from
  the movement's station order. Seaward Crossing is still unvalidated.
- Delay ACCUMULATES along a journey (the 10:15 steam left 10 down and
  reached Blue Anchor 22 down), so matching tolerates growth rather than
  assuming a constant offset.
- Trains run late, not early: an early-looking match is nearly always the
  previous service running late, hence the asymmetric cost.
- Every tuning constant is fitted to this one gala day, which is the most
  atypical day of the year. Re-check them against an ordinary running day.
- Hi-res episode stills are unreliable for classification: even with the
  12s delay they sometimes catch a departing train's rear coach or an
  empty scene. Timing needs per-camera tuning.
- The identity gate is proven by tests but untested at scale: with 3 of 84
  episodes labelled it never fires, because it only helps where identity
  contradicts a chain.
- Episodes recorded before 29/8 evening store only net drift, not the
  train's path, so track-tangent direction cannot be validated against
  them. The watcher now persists a `path` of timestamped centroids; the
  next running day will let the track model be checked properly.
- Jupyter kernel: use "Python (WSR)" (the user's default `python3` kernel
  points at a different project's venv).

## Cautions

- A Gemini API key was leaked in git history (initial commit) — treat as
  burned; a fresh key belongs in `train_detection/.env` (gitignored).
- The Railcam streams are third-party: keep usage polite (one connection
  per camera) and ask before anything public-facing.
- Git identity for this repo is set locally to `dr-harper` (the user's
  personal account) — do not commit here as their work identity.
