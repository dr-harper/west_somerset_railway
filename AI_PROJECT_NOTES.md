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
- `episode_analysis.py`: episodes ↔ timetable matching; unmatched confirmed
  episode = special train. `classify_trains.py`: per-episode Gemini
  classification (structured output).
- Direction vectors in `gala_watcher.py` are PROVISIONAL until validated
  against known services.
- Jupyter kernel: use "Python (WSR)" (the user's default `python3` kernel
  points at a different project's venv).

## Cautions

- A Gemini API key was leaked in git history (initial commit) — treat as
  burned; a fresh key belongs in `train_detection/.env` (gitignored).
- The Railcam streams are third-party: keep usage polite (one connection
  per camera) and ask before anything public-facing.
- Git identity for this repo is set locally to `dr-harper` (the user's
  personal account) — do not commit here as their work identity.
