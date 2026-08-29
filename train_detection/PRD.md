# West Somerset Railway Train Detection — PRD

**Author:** Michael
**Version:** 2.0 — 28th August 2026 (supersedes the June 2024 draft, which
described a trackside sensor system that was never pursued)

## Objective

Detect, classify, and log train movements on the West Somerset Railway using
the six public Railcam webcams, and fuse those observations with the scraped
2026 timetable to give the WSR timetable web app genuine live train data —
something no comparable heritage railway app offers.

## What exists (as of this version)

| Component | File | Status |
| --- | --- | --- |
| Live stream capture (six cameras, HLS via YouTube Live) | `wsr_live_capture.py` | Working |
| Per-camera detection zones (detect / approach / ignore) | `detection_zones.py` | Calibrated at 854×480 |
| Two-tier watcher: motion gate → YOLO11 episodes | `gala_watcher.py` | Dry-run verified; first full run 29th Aug gala |
| Simple interval poller (superseded by the watcher) | `live_poller.py` | Kept for reference |
| Timetable data (scraped from the official WSR calendar) | `../route_data/timetable_2026/` | 59 running days + calendar |
| Web app consuming the timetable | `../app/wsr-railway-app/` | Live on real 2026 data |

## Architecture

```
YouTube Live (6 cams, up to 1080p30)
   └─ tier 1: 480p stream, zone-masked motion gate (~2 Hz, ~7% of one core idle)
        └─ tier 2 (gate open): YOLO11 confirm → episode tracking (~1 Hz)
             ├─ episodes.jsonl  (enter/exit, zones, direction, confidence)
             ├─ captures/       (keyframes, 2 fps clip, one 1080p still)
             └─ [next] classification + timetable matching
```

Design principle: **compute ramps down, not up**. Idle cost is six 480p
decodes; inference only runs while something moves; classification runs once
per episode, not per frame. The target end-state runs on a Raspberry Pi or a
small VPS.

## Roadmap

1. **Episode corpus** — capture the 29th August gala (busiest day of the
   year) end to end. Validate direction vectors against known services.
2. **Classification** — per-episode traction type (steam / diesel / DMU) and
   livery from the 1080p still, via a vision LLM with structured output
   (`classify_trains.py`). Later: distil to a small local classifier using
   timetable-auto-labelled crops.
3. **Timetable matching** — join episodes to scheduled services
   (`episode_analysis.py`); an unmatched confirmed episode is the
   special-train alert.
4. **App integration** — feed matched events to the web app so "live trains"
   reflects reality rather than simulation (backend choice pending).

## Constraints and courtesies

- The streams are Railcam UK's; personal-project use is reasonable, but ask
  before anything public-facing. Do not hammer: one stream per camera.
- Cameras can be repositioned by their operators; zones need a periodic
  reference-frame check.
- No safety claims: this is an enthusiast data project, not railway
  signalling infrastructure.

## Success metrics

| Metric | Target |
| --- | --- |
| Timetabled gala services detected at covered stations | ≥ 90% |
| False episodes per camera per day (moving-train false positives) | ≤ 2 |
| Traction classification accuracy vs timetable ground truth | ≥ 95% |
| Idle CPU (whole watcher, six cameras) | ≤ 10% of one core |
