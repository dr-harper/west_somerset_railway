"""Poll the WSR live webcams and log zone-classified train detections.

Sweeps every camera on an interval, runs YOLO on one frame each, classifies
train detections into the per-camera zones, and appends events to a JSONL
log. Frames with a train in a detect/approach zone are saved to events/ for
review; ignored (stabled-stock) detections are logged but not saved.

Usage:
    python3 live_poller.py --hours 4 --interval 300
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import cv2

from detection_zones import ZONES, classify, draw_zones
from wsr_live_capture import CAMERAS, grab_frame

HERE = Path(__file__).parent
LOG_PATH = HERE / 'poll_log.jsonl'
EVENTS_DIR = HERE / 'events'


def kind_of(camera: str, zone: str | None) -> str | None:
    return next((k for n, k, _ in ZONES[camera] if n == zone), None)


def sweep(model, conf: float, min_live_conf: float) -> list[dict]:
    records = []
    for camera in CAMERAS:
        ts = datetime.now().isoformat(timespec='seconds')
        record = {'ts': ts, 'camera': camera, 'detections': [], 'error': None}
        try:
            frame = grab_frame(camera)
            if frame is None:
                raise RuntimeError('no frame returned')
            results = model(frame, verbose=False, conf=conf)[0]
            interesting = False
            for box in results.boxes:
                cls = model.names[int(box.cls)]
                if cls != 'train':
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
                zone = classify(camera, (cx, cy))
                kind = kind_of(camera, zone)
                record['detections'].append({
                    'conf': round(float(box.conf), 3),
                    'zone': zone,
                    'kind': kind,
                    'box': [x1, y1, x2, y2],
                })
                if kind in ('detect', 'approach') and float(box.conf) >= min_live_conf:
                    interesting = True
            if interesting:
                out = draw_zones(frame, camera)
                for d in record['detections']:
                    x1, y1, x2, y2 = d['box']
                    live = d['kind'] in ('detect', 'approach')
                    colour = (60, 220, 255) if live else (140, 140, 140)
                    cv2.rectangle(out, (x1, y1), (x2, y2), colour, 2)
                    cv2.putText(out, f"train {d['conf']} -> {d['zone']}",
                                (x1, max(14, y1 - 6)),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.42, colour, 1, cv2.LINE_AA)
                stamp = ts.replace(':', '').replace('-', '')
                cv2.imwrite(str(EVENTS_DIR / f'{stamp}_{camera}.jpg'), out)
                record['event_image'] = f'events/{stamp}_{camera}.jpg'
        except Exception as exc:  # keep sweeping the other cameras
            record['error'] = str(exc)[:200]
        records.append(record)
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=float, default=4.0)
    parser.add_argument('--interval', type=int, default=300, help='seconds between sweeps')
    parser.add_argument('--conf', type=float, default=0.35)
    parser.add_argument('--min-live-conf', type=float, default=0.5,
                        help='confidence needed to flag a detect/approach event')
    args = parser.parse_args()

    from ultralytics import YOLO
    model = YOLO(str(HERE / 'yolo11s.pt'))
    EVENTS_DIR.mkdir(exist_ok=True)

    deadline = time.time() + args.hours * 3600
    sweep_no = 0
    while time.time() < deadline:
        sweep_no += 1
        started = time.time()
        records = sweep(model, args.conf, args.min_live_conf)
        with LOG_PATH.open('a') as fh:
            for record in records:
                fh.write(json.dumps(record) + '\n')
        live = sum(1 for r in records for d in r['detections']
                   if d['kind'] in ('detect', 'approach') and d['conf'] >= args.min_live_conf)
        filtered = sum(1 for r in records for d in r['detections']
                       if d['kind'] not in ('detect', 'approach') or d['conf'] < args.min_live_conf)
        errors = sum(1 for r in records if r['error'])
        print(f'sweep {sweep_no} @ {datetime.now():%H:%M:%S}: '
              f'{live} live, {filtered} filtered, {errors} errors, '
              f'{time.time() - started:.0f}s', flush=True)
        remaining = deadline - time.time()
        if remaining <= 0:
            break
        time.sleep(min(max(args.interval - (time.time() - started), 10), remaining))

    print(f'poller finished after {sweep_no} sweeps')


if __name__ == '__main__':
    main()
