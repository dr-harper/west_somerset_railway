"""Two-tier train watcher for the WSR live webcams.

Tier 1 (always on, ~2 Hz, near-zero compute): each camera keeps its HLS
stream open and runs a zone-masked motion gate — downscaled greyscale
frame differencing against a running-average background. Parked stock is
absorbed by the background and never fires the gate.

Tier 2 (only while the gate is open): YOLO confirms a train in a
detect/approach zone, then tracks it at ~1 Hz until it leaves. Each
passage is logged as one episode with enter/exit times, zone history,
centroid drift (=> direction), keyframes, and a low-fps clip.

Designed to ramp down to small compute: the idle cost is six 480p decodes
plus thumbnail maths; inference only runs while something is moving.

Usage:
    python3 gala_watcher.py --hours 11          # e.g. 08:00 -> 19:00
    python3 gala_watcher.py --hours 0.5 --dry-run   # gate test, no YOLO
"""

import argparse
import json
import queue
import threading
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from detection_zones import ZONES, classify, draw_zones
from wsr_live_capture import CAMERAS, resolve_hls_url


def grab_hires_still(camera: str, out_path: Path, delay_s: float = 12.0) -> None:
    """Best-effort 1080p still for classification crops (runs in its own
    thread; the continuous pipeline stays at 480p). Waits a beat so
    approach-zone episodes have the train close to camera, not a speck
    in the distance (lesson from the 08:24 Blue Anchor grab, 29/8)."""
    try:
        time.sleep(delay_s)
        url = resolve_hls_url(camera, format_spec='270/232/231')
        cap = cv2.VideoCapture(url)
        ok, frame = cap.read()
        cap.release()
        if ok:
            cv2.imwrite(str(out_path), frame)
    except Exception:
        pass

HERE = Path(__file__).parent
EPISODES_PATH = HERE / 'episodes.jsonl'
GATE_LOG_PATH = HERE / 'gate_log.jsonl'
CAPTURE_DIR = HERE / 'captures'

# Processing geometry: motion runs at half stream resolution
STREAM_W, STREAM_H = 854, 480
PROC_W, PROC_H = 427, 240
SCALE = PROC_W / STREAM_W

MOTION_SAMPLE_S = 0.5          # tier-1 cadence
YOLO_SAMPLE_S = 1.0            # tier-2 cadence while an episode is active
MOTION_THRESHOLD = 25          # per-pixel absdiff threshold (0-255)
MOTION_FRACTION = 0.02         # fraction of zone mask that must change
MOTION_CONSECUTIVE = 3         # samples needed to open the gate
GLOBAL_JUMP_FRACTION = 0.35    # whole-frame change => exposure/camera jump
CANDIDATE_TIMEOUT_S = 6        # YOLO tries before a gate is called false
EPISODE_GONE_S = 10            # no train for this long closes the episode
BACKGROUND_ALPHA = 0.05        # background adaption rate when idle
URL_REFRESH_S = 4 * 3600       # HLS URLs expire after ~6h; refresh early
CLIP_FPS = 2

# Image-space unit vector meaning "travelling northbound (towards Minehead)".
# PROVISIONAL — sign-check these against the first known timetabled moves.
NORTHBOUND_VECTORS = {
    'minehead_station': (0.0, 1.0),            # arriving = towards camera
    'minehead_seaward_crossing': (-0.95, 0.3), # sign-checked v the 08:10 ex-Minehead 29/8: departing (SB) drifts right
    'blue_anchor': (0.0, -1.0),                # away, towards Dunster
    'watchet_visitor_centre': (-0.2, 0.9),     # sign-checked v the 08:59 NB call 29/8: towards Minehead = down the frame
    'crowcombe_heathfield': (-0.9, -0.45),     # away, towards Stogumber
    'bishops_lydeard': (0.4, -0.9),            # departing, towards the yard
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec='seconds')


def stamp() -> str:
    return datetime.now().strftime('%Y%m%dT%H%M%S')


class SharedDetector:
    """One YOLO instance shared by all camera threads."""

    def __init__(self, weights: str):
        from ultralytics import YOLO
        import torch
        self.device = 'mps' if torch.backends.mps.is_available() else 'cpu'
        self.model = YOLO(weights)
        self.lock = threading.Lock()

    def trains(self, frame, conf=0.4):
        """Return [(conf, (x1,y1,x2,y2), (cx,cy), zone, kind), ...]."""
        with self.lock:
            results = self.model(frame, verbose=False, conf=conf,
                                 device=self.device)[0]
        names = self.model.names
        out = []
        for box in results.boxes:
            if names[int(box.cls)] != 'train':
                continue
            x1, y1, x2, y2 = map(int, box.xyxy[0])
            cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
            out.append((round(float(box.conf), 3), (x1, y1, x2, y2), (cx, cy)))
        return out


class CameraWorker(threading.Thread):
    def __init__(self, camera: str, detector, log_queue, dry_run: bool):
        super().__init__(daemon=True, name=camera)
        self.camera = camera
        self.detector = detector
        self.log_queue = log_queue
        self.dry_run = dry_run
        self.mask = self._build_mask()
        self.background = None
        self.cap = None
        self.url_time = 0.0
        self.consecutive_motion = 0
        self.state = 'IDLE'            # IDLE | CANDIDATE | ACTIVE
        self.state_since = time.time()
        self.last_train_time = 0.0
        self.episode = None
        self.frame_buffer = []         # (t, frame) rolling ~30s at 2 Hz
        self.heartbeat = time.time()
        self.stats = {'gates': 0, 'false_gates': 0, 'episodes': 0,
                      'reconnects': 0, 'jumps': 0}

    # --- setup -----------------------------------------------------------

    def _build_mask(self):
        mask = np.zeros((PROC_H, PROC_W), np.uint8)
        for _name, kind, poly in ZONES.get(self.camera, []):
            if kind in ('detect', 'approach'):
                pts = (np.array(poly, np.float32) * SCALE).astype(np.int32)
                cv2.fillPoly(mask, [pts], 255)
        return mask

    def _connect(self):
        if self.cap is not None:
            self.cap.release()
        url = resolve_hls_url(self.camera)
        self.cap = cv2.VideoCapture(url)
        self.url_time = time.time()
        self.background = None
        self.consecutive_motion = 0

    # --- tier 1: motion gate --------------------------------------------

    def _motion_fraction(self, frame) -> tuple[float, float]:
        small = cv2.resize(frame, (PROC_W, PROC_H))
        grey = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY).astype(np.float32)
        grey = cv2.GaussianBlur(grey, (5, 5), 0)
        if self.background is None:
            self.background = grey.copy()
            return 0.0, 0.0
        diff = cv2.absdiff(grey, self.background)
        changed = (diff > MOTION_THRESHOLD).astype(np.uint8)
        global_frac = float(changed.mean())
        zone_frac = float(changed[self.mask > 0].mean()) if self.mask.any() else 0.0
        # adapt the background only while idle so a dwelling train
        # is not absorbed mid-episode
        if self.state == 'IDLE':
            cv2.accumulateWeighted(grey, self.background, BACKGROUND_ALPHA)
        return zone_frac, global_frac

    # --- tier 2: episodes ------------------------------------------------

    def _start_episode(self, t, detections, frame):
        self.stats['episodes'] += 1
        self.episode = {
            'camera': self.camera,
            't_enter': now_iso(),
            'zones': [],
            'centroids': [],
            'peak_conf': 0.0,
            'keyframes': [],
            'clip_frames': [f for (ft, f) in self.frame_buffer if t - ft <= 6],
        }
        hires_path = CAPTURE_DIR / f'{stamp()}_{self.camera}_hires.jpg'
        self.episode['hires'] = hires_path.name
        threading.Thread(target=grab_hires_still,
                         args=(self.camera, hires_path), daemon=True).start()
        self._observe(t, detections, frame, keyframe=True)

    def _observe(self, t, detections, frame, keyframe=False):
        ep = self.episode
        best = max(detections, key=lambda d: d['conf'])
        ep['centroids'].append((t, best['centre']))
        for d in detections:
            if d['zone'] and d['zone'] not in ep['zones']:
                ep['zones'].append(d['zone'])
        if best['conf'] > ep['peak_conf'] + 0.1 or keyframe:
            ep['peak_conf'] = max(ep['peak_conf'], best['conf'])
            out = draw_zones(frame, self.camera)
            for d in detections:
                x1, y1, x2, y2 = d['box']
                cv2.rectangle(out, (x1, y1), (x2, y2), (60, 220, 255), 2)
                cv2.putText(out, f"train {d['conf']} -> {d['zone']}",
                            (x1, max(14, y1 - 6)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.42, (60, 220, 255), 1, cv2.LINE_AA)
            path = CAPTURE_DIR / f'{stamp()}_{self.camera}_key.jpg'
            cv2.imwrite(str(path), out)
            ep['keyframes'].append(path.name)
        ep['peak_conf'] = max(ep['peak_conf'], best['conf'])
        if len(ep['clip_frames']) < 300:   # cap clip memory on long dwells
            ep['clip_frames'].append(frame)

    def _close_episode(self):
        ep = self.episode
        self.episode = None
        centroids = ep.pop('centroids')
        clip_frames = ep.pop('clip_frames')
        ep['t_exit'] = now_iso()
        ep['n_observations'] = len(centroids)
        if len(centroids) >= 2:
            (t0, (x0, y0)), (t1, (x1, y1)) = centroids[0], centroids[-1]
            drift = (x1 - x0, y1 - y0)
            ep['drift_px'] = drift
            nvec = NORTHBOUND_VECTORS[self.camera]
            dot = drift[0] * nvec[0] + drift[1] * nvec[1]
            magnitude = (drift[0] ** 2 + drift[1] ** 2) ** 0.5
            if magnitude < 30:
                ep['direction'] = 'unclear'
            else:
                ep['direction'] = 'northbound' if dot > 0 else 'southbound'
        else:
            ep['direction'] = 'unclear'
        # low-fps clip for review / future training data
        if clip_frames:
            path = CAPTURE_DIR / f"{stamp()}_{self.camera}_clip.mp4"
            writer = cv2.VideoWriter(str(path),
                                     cv2.VideoWriter_fourcc(*'mp4v'),
                                     CLIP_FPS, (STREAM_W, STREAM_H))
            for f in clip_frames:
                writer.write(f)
            writer.release()
            ep['clip'] = path.name
        self.log_queue.put(('episode', ep))

    # --- main loop -------------------------------------------------------

    def run(self):
        backoff = 2
        last_motion_check = 0.0
        last_yolo = 0.0
        while True:
            try:
                if self.cap is None or time.time() - self.url_time > URL_REFRESH_S:
                    self._connect()
                    backoff = 2
                grabbed = self.cap.grab()
                if not grabbed:
                    raise RuntimeError('stream read failed')
                self.heartbeat = time.time()
                t = time.time()
                if t - last_motion_check < MOTION_SAMPLE_S:
                    continue
                last_motion_check = t
                ok, frame = self.cap.retrieve()
                if not ok:
                    raise RuntimeError('retrieve failed')

                self.frame_buffer.append((t, frame))
                self.frame_buffer = [(ft, f) for ft, f in self.frame_buffer
                                     if t - ft <= 12]

                zone_frac, global_frac = self._motion_fraction(frame)
                if global_frac > GLOBAL_JUMP_FRACTION:
                    # exposure change or camera jump: rebuild background
                    self.stats['jumps'] += 1
                    self.background = None
                    continue

                moving = zone_frac > MOTION_FRACTION
                self.consecutive_motion = self.consecutive_motion + 1 if moving else 0

                if self.state == 'IDLE':
                    if self.consecutive_motion >= MOTION_CONSECUTIVE:
                        self.stats['gates'] += 1
                        self.log_queue.put(('gate', {
                            'ts': now_iso(), 'camera': self.camera,
                            'zone_fraction': round(zone_frac, 4)}))
                        if self.dry_run:
                            self.consecutive_motion = 0
                        else:
                            self.state, self.state_since = 'CANDIDATE', t
                elif self.state == 'CANDIDATE':
                    if t - last_yolo >= YOLO_SAMPLE_S:
                        last_yolo = t
                        detections = self._detect(frame)
                        if detections:
                            self.state, self.state_since = 'ACTIVE', t
                            self.last_train_time = t
                            self._start_episode(t, detections, frame)
                        elif t - self.state_since > CANDIDATE_TIMEOUT_S:
                            self.stats['false_gates'] += 1
                            self.state = 'IDLE'
                elif self.state == 'ACTIVE':
                    if t - last_yolo >= YOLO_SAMPLE_S:
                        last_yolo = t
                        detections = self._detect(frame)
                        if detections:
                            self.last_train_time = t
                            self._observe(t, detections, frame)
                        elif t - self.last_train_time > EPISODE_GONE_S:
                            self._close_episode()
                            self.state = 'IDLE'
            except Exception as exc:
                self.log_queue.put(('error', {
                    'ts': now_iso(), 'camera': self.camera,
                    'error': str(exc)[:200]}))
                self.stats['reconnects'] += 1
                if self.episode:
                    self._close_episode()
                self.state = 'IDLE'
                if self.cap is not None:
                    self.cap.release()
                    self.cap = None
                time.sleep(backoff)
                backoff = min(backoff * 2, 120)

    def _detect(self, frame):
        detections = []
        for conf, box, centre in self.detector.trains(frame):
            zone = classify(self.camera, centre)
            kind = next((k for n, k, _ in ZONES[self.camera] if n == zone), None)
            if kind in ('detect', 'approach') and conf >= 0.5:
                detections.append({'conf': conf, 'box': box,
                                   'centre': centre, 'zone': zone})
        return detections


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--hours', type=float, default=11.0)
    parser.add_argument('--dry-run', action='store_true',
                        help='motion gate only: log gates, never run YOLO')
    args = parser.parse_args()

    CAPTURE_DIR.mkdir(exist_ok=True)
    detector = None if args.dry_run else SharedDetector(str(HERE / 'yolo11s.pt'))
    log_queue: queue.Queue = queue.Queue()
    workers = [CameraWorker(cam, detector, log_queue, args.dry_run)
               for cam in CAMERAS]
    for w in workers:
        w.start()

    deadline = time.time() + args.hours * 3600
    last_report = time.time()
    episode_count = 0
    while time.time() < deadline:
        try:
            kind, payload = log_queue.get(timeout=5)
        except queue.Empty:
            kind = None
        if kind == 'episode':
            episode_count += 1
            with EPISODES_PATH.open('a') as fh:
                fh.write(json.dumps(payload) + '\n')
            print(f"EPISODE {payload['camera']} {payload['t_enter']} -> "
                  f"{payload['t_exit']} {payload.get('direction')} "
                  f"zones={payload['zones']} peak={payload['peak_conf']}",
                  flush=True)
        elif kind in ('gate', 'error'):
            with GATE_LOG_PATH.open('a') as fh:
                fh.write(json.dumps({'kind': kind, **payload}) + '\n')
        if time.time() - last_report > 600:
            last_report = time.time()
            summary = {w.camera: dict(w.stats,
                                      state=w.state,
                                      stale=round(time.time() - w.heartbeat))
                       for w in workers}
            print(f'--- {datetime.now():%H:%M:%S} status: '
                  + json.dumps(summary), flush=True)

    print(f'watcher finished: {episode_count} episodes')


if __name__ == '__main__':
    main()
